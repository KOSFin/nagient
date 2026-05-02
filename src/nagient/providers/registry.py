from __future__ import annotations

import importlib.util
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from nagient.domain.entities.config_fields import ConfigFieldSpec
from nagient.domain.entities.system_state import CheckIssue
from nagient.providers.base import (
    REQUIRED_PROVIDER_METHODS,
    BaseProviderPlugin,
    LoadedProviderPlugin,
    ProviderPluginManifest,
)
from nagient.providers.builtin import builtin_providers


@dataclass(frozen=True)
class ProviderDiscovery:
    plugins: dict[str, LoadedProviderPlugin] = field(default_factory=dict)
    issues: list[CheckIssue] = field(default_factory=list)


class ProviderPluginRegistry:
    def discover(self, providers_dir: Path) -> ProviderDiscovery:
        plugins = {
            plugin.manifest.plugin_id: plugin
            for plugin in builtin_providers()
        }
        issues: list[CheckIssue] = []

        if not providers_dir.exists():
            return ProviderDiscovery(plugins=plugins, issues=issues)

        for entry in sorted(providers_dir.iterdir()):
            if not entry.is_dir():
                continue
            manifest_path = entry / "provider.toml"
            if not manifest_path.exists():
                continue
            try:
                plugin = self._load_plugin(entry)
            except Exception as exc:
                issues.append(
                    CheckIssue(
                        severity="warning",
                        code="provider_plugin.load_failed",
                        message=f"Failed to load provider plugin from {entry.name!r}: {exc}",
                        source=entry.name,
                        hint="Fix provider.toml or provider.py before enabling this plugin.",
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
                        code="provider_plugin.duplicate_id",
                        message=(
                            f"Provider plugin id {plugin_id!r} shadows an existing plugin "
                            "and was skipped."
                        ),
                        source=entry.name,
                    )
                )
                continue
            plugins[plugin_id] = plugin

        return ProviderDiscovery(plugins=plugins, issues=issues)

    def _load_plugin(self, directory: Path) -> LoadedProviderPlugin:
        manifest = self._parse_manifest(directory / "provider.toml")
        module_path = directory / manifest.entrypoint
        if not module_path.exists():
            raise ValueError(f"Entrypoint file {manifest.entrypoint!r} does not exist.")

        module_name = f"nagient_user_provider_{directory.name.replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Cannot create import spec for {module_path}.")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        factory = getattr(module, "build_plugin", None)
        if not callable(factory):
            raise ValueError("Provider entrypoint must export callable build_plugin().")

        implementation = factory()
        if not isinstance(implementation, BaseProviderPlugin):
            raise ValueError(
                "Provider entrypoint build_plugin() must return BaseProviderPlugin."
            )
        return LoadedProviderPlugin(
            manifest=manifest,
            implementation=implementation,
            source=str(directory),
        )

    def _parse_manifest(self, manifest_path: Path) -> ProviderPluginManifest:
        payload = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("provider.toml must define a TOML object.")

        plugin_type = _require_string(payload, "type")
        if plugin_type != "provider":
            raise ValueError(f"Unsupported provider plugin type {plugin_type!r}.")

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

        return ProviderPluginManifest(
            plugin_id=_require_string(payload, "id"),
            display_name=_require_string(payload, "display_name"),
            version=_require_string(payload, "version"),
            family=_require_string(payload, "family"),
            entrypoint=_require_string(payload, "entrypoint"),
            supported_auth_modes=_require_string_list(payload.get("supported_auth_modes")),
            default_auth_mode=_require_string(payload, "default_auth_mode"),
            capabilities=_require_string_list(payload.get("capabilities")),
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
            secret_config=_merge_string_keys(
                _require_string_list(payload.get("secret_config")),
                [field.key for field in config_fields if field.secret],
            ),
            credential_fields=_require_string_list(payload.get("credential_fields")),
            config_fields=config_fields,
            config_schema_file=config_schema_file,
        )

    def _validate_plugin(self, plugin: LoadedProviderPlugin) -> list[CheckIssue]:
        issues: list[CheckIssue] = []
        manifest = plugin.manifest
        implementation = plugin.implementation

        if manifest.default_auth_mode not in manifest.supported_auth_modes:
            issues.append(
                CheckIssue(
                    severity="error",
                    code="provider_plugin.invalid_default_auth_mode",
                    message=(
                        f"Provider plugin {manifest.plugin_id!r} uses default_auth_mode "
                        f"{manifest.default_auth_mode!r}, but it is not listed in "
                        "supported_auth_modes."
                    ),
                    source=manifest.plugin_id,
                )
            )

        for method_name in REQUIRED_PROVIDER_METHODS:
            if not callable(getattr(implementation, method_name, None)):
                issues.append(
                    CheckIssue(
                        severity="error",
                        code="provider_plugin.missing_method",
                        message=(
                            f"Provider plugin {manifest.plugin_id!r} does not expose "
                            f"callable method {method_name!r}."
                        ),
                        source=manifest.plugin_id,
                    )
                )
        return issues


def _require_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Provider plugin field {key!r} must be a non-empty string.")
    return value


def _require_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("Provider plugin lists must contain only strings.")
    return list(value)


def _parse_config_fields(value: object) -> list[ConfigFieldSpec]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Provider plugin config_fields must be a list of TOML tables.")
    config_fields: list[ConfigFieldSpec] = []
    seen: set[str] = set()
    for raw_field in value:
        if not isinstance(raw_field, dict):
            raise ValueError("Each provider config_fields entry must be a table.")
        key = _require_string(raw_field, "key")
        if key in seen:
            raise ValueError(f"Duplicate provider config field {key!r}.")
        seen.add(key)
        config_fields.append(
            ConfigFieldSpec(
                key=key,
                label=_optional_string(raw_field.get("label")),
                help_text=_optional_string(raw_field.get("help_text")),
                value_type=_optional_string(raw_field.get("value_type")) or "string",
                category=_optional_string(raw_field.get("category")) or "advanced",
                required=bool(raw_field.get("required", False)),
                secret=bool(raw_field.get("secret", False)),
            )
        )
    return config_fields


def _optional_string(value: object) -> str:
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
    for config_field in fields:
        if config_field.required != required:
            continue
        if config_field.key not in seen:
            merged.append(config_field.key)
            seen.add(config_field.key)
    return merged


def _merge_string_keys(
    explicit_keys: list[str],
    derived_keys: list[str],
) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for key in [*explicit_keys, *derived_keys]:
        if key not in seen:
            merged.append(key)
            seen.add(key)
    return merged
