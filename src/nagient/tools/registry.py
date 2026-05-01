from __future__ import annotations

import importlib.util
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from nagient.domain.entities.config_fields import ConfigFieldSpec
from nagient.domain.entities.system_state import CheckIssue
from nagient.domain.entities.tooling import ToolFunctionManifest, ToolPluginManifest
from nagient.tools.base import BaseToolPlugin, LoadedToolPlugin
from nagient.tools.builtin import builtin_tools


@dataclass(frozen=True)
class ToolDiscovery:
    plugins: dict[str, LoadedToolPlugin] = field(default_factory=dict)
    issues: list[CheckIssue] = field(default_factory=list)


class ToolPluginRegistry:
    def discover(self, tools_dir: Path) -> ToolDiscovery:
        plugins = {plugin.manifest.plugin_id: plugin for plugin in builtin_tools()}
        issues: list[CheckIssue] = []

        if not tools_dir.exists():
            return ToolDiscovery(plugins=plugins, issues=issues)

        for entry in sorted(tools_dir.iterdir()):
            if not entry.is_dir():
                continue
            manifest_path = entry / "tool.toml"
            if not manifest_path.exists():
                continue
            try:
                plugin = self._load_plugin(entry)
            except Exception as exc:
                issues.append(
                    CheckIssue(
                        severity="warning",
                        code="tool_plugin.load_failed",
                        message=f"Failed to load tool plugin from {entry.name!r}: {exc}",
                        source=entry.name,
                    )
                )
                continue

            validation_issues = self._validate_plugin(plugin)
            issues.extend(validation_issues)
            if any(issue.severity == "error" for issue in validation_issues):
                continue

            plugin_id = plugin.manifest.plugin_id
            if plugin_id in plugins:
                issues.append(
                    CheckIssue(
                        severity="warning",
                        code="tool_plugin.duplicate_id",
                        message=(
                            f"Tool plugin id {plugin_id!r} shadows an existing plugin and "
                            "was skipped."
                        ),
                        source=entry.name,
                    )
                )
                continue
            plugins[plugin_id] = plugin

        return ToolDiscovery(plugins=plugins, issues=issues)

    def _load_plugin(self, directory: Path) -> LoadedToolPlugin:
        manifest = self._parse_manifest(directory / "tool.toml")
        module_path = directory / manifest.entrypoint
        if not module_path.exists():
            raise ValueError(f"Entrypoint file {manifest.entrypoint!r} does not exist.")

        module_name = f"nagient_user_tool_{directory.name.replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Cannot create import spec for {module_path}.")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        factory = getattr(module, "build_plugin", None)
        if not callable(factory):
            raise ValueError("Tool entrypoint must export callable build_plugin().")

        implementation = factory()
        if not isinstance(implementation, BaseToolPlugin):
            raise ValueError("build_plugin() must return BaseToolPlugin.")
        return LoadedToolPlugin(
            manifest=manifest,
            implementation=implementation,
            source=str(directory),
        )

    def _parse_manifest(self, manifest_path: Path) -> ToolPluginManifest:
        payload = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("tool.toml must define a TOML object.")

        plugin_type = _require_string(payload, "type")
        if plugin_type != "tool":
            raise ValueError(f"Unsupported tool plugin type {plugin_type!r}.")

        config_schema_file: str | None = None
        if "config_schema_file" in payload:
            config_schema_path = manifest_path.parent / _require_string(
                payload,
                "config_schema_file",
            )
            if not config_schema_path.exists():
                raise ValueError(
                    f"Config schema file {config_schema_path.name!r} does not exist."
                )
            config_schema_file = config_schema_path.name

        raw_functions = payload.get("functions")
        if not isinstance(raw_functions, list):
            raise ValueError("Tool plugin must define a [[functions]] list.")

        functions: list[ToolFunctionManifest] = []
        for raw_function in raw_functions:
            if not isinstance(raw_function, dict):
                raise ValueError("Each tool function entry must be a table.")
            functions.append(
                ToolFunctionManifest(
                    function_name=_require_string(raw_function, "name"),
                    binding=_require_string(raw_function, "binding"),
                    description=_require_string(raw_function, "description"),
                    input_schema=_require_mapping(raw_function.get("input_schema")),
                    output_schema=_require_mapping(raw_function.get("output_schema")),
                    permissions=_require_string_list(raw_function.get("permissions")),
                    required_config=_require_string_list(raw_function.get("required_config")),
                    optional_config=_require_string_list(raw_function.get("optional_config")),
                    secret_bindings=_require_string_list(raw_function.get("secret_bindings")),
                    required_connectors=_require_string_list(
                        raw_function.get("required_connectors")
                    ),
                    side_effect=_string_or_default(raw_function.get("side_effect"), "read"),
                    approval_policy=_string_or_default(
                        raw_function.get("approval_policy"),
                        "never",
                    ),
                    dry_run_supported=bool(raw_function.get("dry_run_supported", False)),
                )
            )

        return ToolPluginManifest(
            plugin_id=_require_string(payload, "id"),
            display_name=_require_string(payload, "display_name"),
            version=_require_string(payload, "version"),
            namespace=_require_string(payload, "namespace"),
            entrypoint=_require_string(payload, "entrypoint"),
            functions=functions,
            required_config=_merge_config_keys(
                _require_string_list(payload.get("required_config")),
                config_fields := _parse_config_fields(payload.get("config_fields")),
                required=True,
            ),
            optional_config=_merge_config_keys(
                _require_string_list(payload.get("optional_config")),
                config_fields,
                required=False,
            ),
            config_fields=config_fields,
            capabilities=_require_string_list(payload.get("capabilities")),
            healthcheck_binding=_optional_string(payload.get("healthcheck_binding")),
            selftest_binding=_optional_string(payload.get("selftest_binding")),
            config_schema_file=config_schema_file,
        )

    def _validate_plugin(self, plugin: LoadedToolPlugin) -> list[CheckIssue]:
        issues: list[CheckIssue] = []
        implementation = plugin.implementation
        manifest = plugin.manifest
        if not manifest.functions:
            issues.append(
                CheckIssue(
                    severity="error",
                    code="tool_plugin.no_functions",
                    message=f"Tool plugin {manifest.plugin_id!r} does not declare any functions.",
                    source=manifest.plugin_id,
                )
            )
        for function in manifest.functions:
            if not callable(getattr(implementation, function.binding, None)):
                issues.append(
                    CheckIssue(
                        severity="error",
                        code="tool_plugin.binding_not_callable",
                        message=(
                            f"Tool function {function.function_name!r} is bound to "
                            f"{function.binding!r}, but the attribute is not callable."
                        ),
                        source=manifest.plugin_id,
                    )
                )
        for binding_name in [manifest.healthcheck_binding, manifest.selftest_binding]:
            if binding_name and not callable(getattr(implementation, binding_name, None)):
                issues.append(
                    CheckIssue(
                        severity="error",
                        code="tool_plugin.invalid_optional_binding",
                        message=(
                            f"Tool plugin {manifest.plugin_id!r} references optional binding "
                            f"{binding_name!r}, but it is not callable."
                        ),
                        source=manifest.plugin_id,
                    )
                )
        return issues


def _require_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Tool plugin field {key!r} must be a non-empty string.")
    return value


def _optional_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _require_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("Tool plugin lists must contain only strings.")
    return list(value)


def _require_mapping(value: object) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Tool schema payloads must be TOML tables.")
    return {str(key): item for key, item in value.items()}


def _string_or_default(value: object, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return default


def _parse_config_fields(value: object) -> list[ConfigFieldSpec]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Tool plugin config_fields must be a list of TOML tables.")
    config_fields: list[ConfigFieldSpec] = []
    seen: set[str] = set()
    for raw_field in value:
        if not isinstance(raw_field, dict):
            raise ValueError("Each tool config_fields entry must be a table.")
        key = _require_string(raw_field, "key")
        if key in seen:
            raise ValueError(f"Duplicate tool config field {key!r}.")
        seen.add(key)
        config_fields.append(
            ConfigFieldSpec(
                key=key,
                label=_optional_text(raw_field.get("label")),
                help_text=_optional_text(raw_field.get("help_text")),
                value_type=_optional_text(raw_field.get("value_type")) or "string",
                category=_optional_text(raw_field.get("category")) or "advanced",
                required=bool(raw_field.get("required", False)),
                secret=bool(raw_field.get("secret", False)),
            )
        )
    return config_fields


def _optional_text(value: object) -> str:
    if isinstance(value, str):
        return value
    return ""


def _merge_config_keys(
    explicit_keys: list[str],
    fields: list[ConfigFieldSpec],
    *,
    required: bool,
) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for key in explicit_keys:
        if key not in seen:
            merged.append(key)
            seen.add(key)
    for field in fields:
        if field.required != required:
            continue
        if field.key not in seen:
            merged.append(field.key)
            seen.add(field.key)
    return merged
