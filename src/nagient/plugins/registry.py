from __future__ import annotations

import importlib.util
import shlex
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from nagient.domain.entities.config_fields import ConfigFieldSpec
from nagient.domain.entities.logging import PluginLogChannelSpec
from nagient.domain.entities.system_state import CheckIssue
from nagient.plugins.base import (
    REQUIRED_TRANSPORT_SLOTS,
    BaseTransportPlugin,
    LoadedTransportPlugin,
    TransportPluginManifest,
)
from nagient.plugins.dependencies import activate_plugin_dependencies, plugin_python
from nagient.plugins.process_adapter import ExternalProcessTransportPlugin


@dataclass(frozen=True)
class PluginDiscovery:
    plugins: dict[str, LoadedTransportPlugin] = field(default_factory=dict)
    issues: list[CheckIssue] = field(default_factory=list)


class TransportPluginRegistry:
    def discover(self, plugins_dir: Path) -> PluginDiscovery:
        plugins: dict[str, LoadedTransportPlugin] = {}
        issues: list[CheckIssue] = []

        bundled_transports_dir = Path(__file__).resolve().parents[1] / "bundled_transports"
        self._discover_directory(bundled_transports_dir, plugins, issues)

        if not plugins_dir.exists():
            return PluginDiscovery(plugins=plugins, issues=issues)

        self._discover_directory(plugins_dir, plugins, issues)

        return PluginDiscovery(plugins=plugins, issues=issues)

    def _discover_directory(
        self,
        plugins_dir: Path,
        plugins: dict[str, LoadedTransportPlugin],
        issues: list[CheckIssue],
    ) -> None:
        if not plugins_dir.exists():
            return

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

    def _load_plugin(self, directory: Path) -> LoadedTransportPlugin:
        manifest_path = directory / "plugin.toml"
        manifest = self._parse_manifest(manifest_path)
        payload = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        activate_plugin_dependencies(directory)
        runtime = _runtime_or_default(payload.get("runtime"))
        if runtime == "process":
            implementation = ExternalProcessTransportPlugin(
                command=_process_command(payload, directory, manifest.entrypoint),
                cwd=directory,
                timeout_seconds=_positive_int(payload.get("process_timeout_seconds"), 30),
            )
            return LoadedTransportPlugin(
                manifest=manifest,
                implementation=implementation,
                source=str(directory),
                runtime=runtime,
            )

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
            runtime=runtime,
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
            config_fields=config_fields,
            instruction_template=instruction_template,
            config_schema_file=config_schema_file,
            runtime=_runtime_or_default(payload.get("runtime")),
            default_target_field=_optional_string(payload.get("default_target_field")),
            default_target_config_key=_optional_string(
                payload.get("default_target_config_key"),
            ),
            default_target_always_available=bool(
                payload.get("default_target_always_available", False),
            ),
            send_message_hint=_optional_string(payload.get("send_message_hint")),
            interaction_capabilities=_require_string_list(
                payload.get("interaction_capabilities")
            ),
            interaction_functions=_require_string_mapping_or_empty(
                payload.get("interaction_functions")
            ),
            log_channels=_parse_log_channels(payload.get("log_channels")),
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

        for capability, exposed_name in manifest.interaction_functions.items():
            if capability not in manifest.interaction_capabilities:
                issues.append(
                    CheckIssue(
                        severity="error",
                        code="plugin.interaction_function_without_capability",
                        message=(
                            f"Plugin {manifest.plugin_id!r} maps interaction capability "
                            f"{capability!r} without declaring it."
                        ),
                        source=manifest.plugin_id,
                    )
                )
            if exposed_name not in manifest.function_bindings:
                issues.append(
                    CheckIssue(
                        severity="error",
                        code="plugin.interaction_function_not_bound",
                        message=(
                            f"Plugin {manifest.plugin_id!r} maps interaction capability "
                            f"{capability!r} to unknown function {exposed_name!r}."
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


def _require_string_mapping_or_empty(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        msg = "Plugin interaction_functions must be a table."
        raise ValueError(msg)
    mapping: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Plugin interaction function keys must be non-empty strings.")
        if not isinstance(item, str) or not item.strip():
            raise ValueError("Plugin interaction function values must be non-empty strings.")
        mapping[key.strip()] = item.strip()
    return mapping


def _require_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        msg = "Plugin lists must contain only strings."
        raise ValueError(msg)
    return list(value)


def _parse_config_fields(value: object) -> list[ConfigFieldSpec]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Plugin config_fields must be a list of TOML tables.")
    config_fields: list[ConfigFieldSpec] = []
    seen: set[str] = set()
    for raw_field in value:
        if not isinstance(raw_field, dict):
            raise ValueError("Each plugin config_fields entry must be a table.")
        key = _require_string(raw_field, "key")
        if key in seen:
            raise ValueError(f"Duplicate plugin config field {key!r}.")
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


def _parse_log_channels(value: object) -> list[PluginLogChannelSpec]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Plugin log_channels must be a list of TOML tables.")
    channels: list[PluginLogChannelSpec] = []
    seen: set[str] = set()
    for raw_channel in value:
        if not isinstance(raw_channel, dict):
            raise ValueError("Each plugin log_channels entry must be a table.")
        name = _require_string(raw_channel, "name")
        if name in seen:
            raise ValueError(f"Duplicate plugin log channel {name!r}.")
        seen.add(name)
        level = _optional_string(raw_channel.get("default_level")) or "info"
        if level not in {"debug", "info", "warning", "error"}:
            raise ValueError(
                "Plugin log channel default_level must be debug, info, warning, or "
                "error."
            )
        channels.append(
            PluginLogChannelSpec(
                name=name,
                description=_optional_string(raw_channel.get("description")),
                default_level=level,
            )
        )
    return channels


def _optional_string(value: object) -> str:
    if isinstance(value, str):
        return value
    return ""


def _runtime_or_default(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return "python"
    normalized = value.strip().lower().replace("_", "-")
    if normalized in {"python", "process"}:
        return normalized
    raise ValueError("Transport plugin runtime must be 'python' or 'process'.")


def _process_command(payload: dict[str, object], directory: Path, entrypoint: str) -> list[str]:
    raw_command = payload.get("command")
    if isinstance(raw_command, list) and all(isinstance(item, str) for item in raw_command):
        return [str(item) for item in raw_command]
    if isinstance(raw_command, str) and raw_command.strip():
        return shlex.split(raw_command)

    entrypoint_path = directory / entrypoint
    if not entrypoint_path.exists():
        raise ValueError(f"Process entrypoint file {entrypoint!r} does not exist.")
    if _is_executable(entrypoint_path):
        return [str(entrypoint_path)]
    suffix = entrypoint_path.suffix.lower()
    if suffix == ".py":
        return [plugin_python(directory), str(entrypoint_path)]
    if suffix in {".sh", ".bash"}:
        return ["sh", str(entrypoint_path)]
    return [str(entrypoint_path)]


def _is_executable(path: Path) -> bool:
    return path.exists() and path.is_file() and path.stat().st_mode & 0o111 != 0


def _positive_int(value: object, default: int) -> int:
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        if parsed > 0:
            return parsed
    return default


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
