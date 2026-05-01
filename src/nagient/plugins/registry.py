from __future__ import annotations

import importlib.util
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from nagient.domain.entities.system_state import CheckIssue
from nagient.plugins.base import (
    REQUIRED_TRANSPORT_SLOTS,
    BaseTransportPlugin,
    LoadedTransportPlugin,
    TransportPluginManifest,
)
from nagient.plugins.builtin import builtin_plugins


@dataclass(frozen=True)
class PluginDiscovery:
    plugins: dict[str, LoadedTransportPlugin] = field(default_factory=dict)
    issues: list[CheckIssue] = field(default_factory=list)


class TransportPluginRegistry:
    def discover(self, plugins_dir: Path) -> PluginDiscovery:
        plugins = {
            plugin.manifest.plugin_id: plugin
            for plugin in builtin_plugins()
        }
        issues: list[CheckIssue] = []

        if not plugins_dir.exists():
            return PluginDiscovery(plugins=plugins, issues=issues)

        for entry in sorted(plugins_dir.iterdir()):
            if not entry.is_dir():
                continue
            manifest_path = entry / "plugin.toml"
            if not manifest_path.exists():
                continue
            try:
                plugin = self._load_plugin(entry)
            except Exception as exc:
                issues.append(
                    CheckIssue(
                        severity="warning",
                        code="plugin.load_failed",
                        message=f"Failed to load plugin from {entry.name!r}: {exc}",
                        source=entry.name,
                        hint="Fix plugin.toml or transport.py before enabling this plugin.",
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
                        code="plugin.duplicate_id",
                        message=(
                            f"Plugin id {plugin_id!r} shadows an existing plugin and "
                            "was skipped."
                        ),
                        source=entry.name,
                    )
                )
                continue
            plugins[plugin_id] = plugin

        return PluginDiscovery(plugins=plugins, issues=issues)

    def _load_plugin(self, directory: Path) -> LoadedTransportPlugin:
        manifest = self._parse_manifest(directory / "plugin.toml")
        module_path = directory / manifest.entrypoint
        if not module_path.exists():
            msg = f"Entrypoint file {manifest.entrypoint!r} does not exist."
            raise ValueError(msg)

        module_name = f"nagient_user_plugin_{directory.name.replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            msg = f"Cannot create import spec for {module_path}."
            raise ValueError(msg)

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        factory = getattr(module, "build_plugin", None)
        if not callable(factory):
            msg = "Plugin entrypoint must export callable build_plugin()."
            raise ValueError(msg)

        implementation = factory()
        if not isinstance(implementation, BaseTransportPlugin):
            msg = "Plugin entrypoint build_plugin() must return BaseTransportPlugin."
            raise ValueError(msg)
        return LoadedTransportPlugin(
            manifest=manifest,
            implementation=implementation,
            source=str(directory),
        )

    def _parse_manifest(self, manifest_path: Path) -> TransportPluginManifest:
        payload = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            msg = "plugin.toml must define a TOML object."
            raise ValueError(msg)

        plugin_type = _require_string(payload, "type")
        if plugin_type != "transport":
            msg = f"Unsupported plugin type {plugin_type!r}."
            raise ValueError(msg)

        instructions_file = manifest_path.parent / _require_string(payload, "instructions_file")
        instruction_template = instructions_file.read_text(encoding="utf-8")

        config_schema_file: str | None = None
        if "config_schema_file" in payload:
            config_schema_path = manifest_path.parent / _require_string(
                payload,
                "config_schema_file",
            )
            if not config_schema_path.exists():
                msg = f"Config schema file {config_schema_path.name!r} does not exist."
                raise ValueError(msg)
            config_schema_file = config_schema_path.name

        return TransportPluginManifest(
            plugin_id=_require_string(payload, "id"),
            display_name=_require_string(payload, "display_name"),
            version=_require_string(payload, "version"),
            namespace=_require_string(payload, "namespace"),
            entrypoint=_require_string(payload, "entrypoint"),
            required_slots=_require_string_mapping(payload, "required_slots"),
            function_bindings=_require_string_mapping(payload, "function_bindings"),
            custom_functions=_require_string_list(payload.get("custom_functions")),
            required_config=_require_string_list(payload.get("required_config")),
            optional_config=_require_string_list(payload.get("optional_config")),
            secret_config=_require_string_list(payload.get("secret_config")),
            instruction_template=instruction_template,
            config_schema_file=config_schema_file,
        )

    def _validate_plugin(self, plugin: LoadedTransportPlugin) -> list[CheckIssue]:
        issues: list[CheckIssue] = []
        manifest = plugin.manifest
        implementation = plugin.implementation

        missing_slots = sorted(set(REQUIRED_TRANSPORT_SLOTS) - set(manifest.required_slots))
        if missing_slots:
            issues.append(
                CheckIssue(
                    severity="error",
                    code="plugin.missing_required_slots",
                    message=(
                        f"Plugin {manifest.plugin_id!r} is missing required slots: "
                        f"{', '.join(missing_slots)}."
                    ),
                    source=manifest.plugin_id,
                )
            )

        for slot_name, exposed_name in manifest.required_slots.items():
            if exposed_name not in manifest.function_bindings:
                issues.append(
                    CheckIssue(
                        severity="error",
                        code="plugin.slot_not_bound",
                        message=(
                            f"Plugin {manifest.plugin_id!r} declares slot {slot_name!r} "
                            f"without a matching function binding for {exposed_name!r}."
                        ),
                        source=manifest.plugin_id,
                    )
                )

        for exposed_name in manifest.custom_functions:
            if exposed_name not in manifest.function_bindings:
                issues.append(
                    CheckIssue(
                        severity="error",
                        code="plugin.custom_function_not_bound",
                        message=(
                            f"Plugin {manifest.plugin_id!r} declares custom function "
                            f"{exposed_name!r} without a matching binding."
                        ),
                        source=manifest.plugin_id,
                    )
                )

        for exposed_name, attribute_name in manifest.function_bindings.items():
            attribute = getattr(implementation, attribute_name, None)
            if not callable(attribute):
                issues.append(
                    CheckIssue(
                        severity="error",
                        code="plugin.binding_not_callable",
                        message=(
                            f"Plugin {manifest.plugin_id!r} binds {exposed_name!r} to "
                            f"{attribute_name!r}, but the attribute is not callable."
                        ),
                        source=manifest.plugin_id,
                    )
                )

        return issues


def _require_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        msg = f"Plugin field {key!r} must be a non-empty string."
        raise ValueError(msg)
    return value


def _require_string_mapping(payload: dict[str, object], key: str) -> dict[str, str]:
    value = payload.get(key)
    if not isinstance(value, dict):
        msg = f"Plugin field {key!r} must be a table."
        raise ValueError(msg)
    mapping: dict[str, str] = {}
    for item_key, item_value in value.items():
        if not isinstance(item_key, str) or not isinstance(item_value, str):
            msg = f"Plugin field {key!r} must contain only string pairs."
            raise ValueError(msg)
        mapping[item_key] = item_value
    return mapping


def _require_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        msg = "Plugin lists must contain only strings."
        raise ValueError(msg)
    return list(value)
