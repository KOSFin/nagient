from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import nagient.providers.scaffold as provider_scaffold
from nagient.app.configuration import (
    _coerce_bool,
    _ensure_mapping,
    default_system_prompt_file,
    read_raw_config,
    render_credentials_readme,
    render_default_config,
    render_default_secrets,
    render_default_system_prompt,
    render_default_tool_secrets,
    render_plugins_readme,
    render_providers_readme,
    render_tools_readme,
    write_raw_config,
)
from nagient.app.settings import Settings
from nagient.plugins.scaffold import ScaffoldResult, scaffold_transport_plugin
from nagient.tools.scaffold import ScaffoldResult as ToolScaffoldResult
from nagient.tools.scaffold import scaffold_tool_plugin


@dataclass(frozen=True)
class ConfigurationService:
    settings: Settings
    transport_registry: Any | None = None
    provider_registry: Any | None = None
    tool_registry: Any | None = None
    provider_service: Any | None = None

    _SECRET_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def initialize(self, force: bool = False) -> dict[str, object]:
        self.settings.ensure_directories()
        written_files: list[str] = []

        file_payloads = {
            self.settings.config_file: render_default_config(self.settings),
            self.settings.secrets_file: render_default_secrets(),
            self.settings.tool_secrets_file: render_default_tool_secrets(),
            default_system_prompt_file(self.settings): render_default_system_prompt(),
            self.settings.plugins_dir / "README.md": render_plugins_readme(),
            self.settings.tools_dir / "README.md": render_tools_readme(),
            self.settings.providers_dir / "README.md": render_providers_readme(),
            self.settings.credentials_dir / "README.md": render_credentials_readme(),
        }
        for path, content in file_payloads.items():
            if path.exists() and not force:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            written_files.append(str(path))

        return {
            "home_dir": str(self.settings.home_dir),
            "config_file": str(self.settings.config_file),
            "secrets_file": str(self.settings.secrets_file),
            "tool_secrets_file": str(self.settings.tool_secrets_file),
            "prompts_dir": str(self.settings.prompts_dir),
            "plugins_dir": str(self.settings.plugins_dir),
            "tools_dir": str(self.settings.tools_dir),
            "providers_dir": str(self.settings.providers_dir),
            "credentials_dir": str(self.settings.credentials_dir),
            "force": force,
            "written_files": written_files,
        }

    def scaffold_transport(
        self,
        plugin_id: str,
        output_dir: Path | None = None,
        force: bool = False,
    ) -> ScaffoldResult:
        target_dir = output_dir or self.settings.plugins_dir / plugin_id
        return scaffold_transport_plugin(
            plugin_id=plugin_id,
            output_dir=target_dir,
            force=force,
        )

    def scaffold_tool(
        self,
        plugin_id: str,
        output_dir: Path | None = None,
        force: bool = False,
    ) -> ToolScaffoldResult:
        target_dir = output_dir or self.settings.tools_dir / plugin_id
        return scaffold_tool_plugin(
            plugin_id=plugin_id,
            output_dir=target_dir,
            force=force,
        )

    def scaffold_provider(
        self,
        plugin_id: str,
        output_dir: Path | None = None,
        force: bool = False,
    ) -> provider_scaffold.ScaffoldResult:
        target_dir = output_dir or self.settings.providers_dir / plugin_id
        return provider_scaffold.scaffold_provider_plugin(
            plugin_id=plugin_id,
            output_dir=target_dir,
            force=force,
        )

    def configure_provider(
        self,
        provider_id: str,
        *,
        plugin_id: str | None = None,
        enabled: bool | None = None,
        default: bool | None = None,
        config_updates: dict[str, object] | None = None,
    ) -> dict[str, object]:
        raw_config = read_raw_config(self.settings.config_file)
        providers = _ensure_mapping(raw_config, "providers")
        profile = providers.get(provider_id)
        if not isinstance(profile, dict):
            profile = {}

        resolved_plugin_id = self._resolve_component_plugin_id(
            existing_plugin_id=profile.get("plugin"),
            requested_plugin_id=plugin_id,
            fallback_plugin_id=f"builtin.{provider_id}",
        )
        manifest = self._require_provider_manifest(resolved_plugin_id)
        self._validate_component_updates(
            kind="provider",
            component_id=provider_id,
            allowed_keys=set(manifest.required_config)
            | set(manifest.optional_config)
            | {"plugin", "enabled"},
            updates=config_updates or {},
        )
        self._validate_secret_reference_updates(
            kind="provider",
            component_id=provider_id,
            secret_keys=set(manifest.secret_config),
            updates=config_updates or {},
        )

        profile["plugin"] = resolved_plugin_id
        if enabled is not None:
            profile["enabled"] = enabled
        for key, value in (config_updates or {}).items():
            profile[key] = value
        providers[provider_id] = profile

        agent = _ensure_mapping(raw_config, "agent")
        if default is True:
            agent["default_provider"] = provider_id
            agent["require_provider"] = True
        elif default is False and str(agent.get("default_provider", "")).strip() == provider_id:
            agent["default_provider"] = ""
            agent["require_provider"] = False
        elif default is None and not str(agent.get("default_provider", "")).strip():
            enabled_provider_ids = [
                candidate_id
                for candidate_id, candidate_profile in providers.items()
                if isinstance(candidate_id, str)
                and isinstance(candidate_profile, dict)
                and _coerce_bool(candidate_profile.get("enabled", False))
            ]
            if len(enabled_provider_ids) == 1:
                agent["default_provider"] = enabled_provider_ids[0]

        write_raw_config(self.settings.config_file, raw_config)
        return {
            "component": "provider",
            "provider_id": provider_id,
            "plugin_id": resolved_plugin_id,
            "enabled": profile.get("enabled", False),
            "default": str(agent.get("default_provider", "")).strip() == provider_id,
            "config": {str(key): value for key, value in profile.items() if key != "plugin"},
            "required_config": manifest.required_config,
            "optional_config": manifest.optional_config,
            "config_fields": [field_spec.to_dict() for field_spec in manifest.config_fields],
        }

    def configure_transport(
        self,
        transport_id: str,
        *,
        plugin_id: str | None = None,
        enabled: bool | None = None,
        config_updates: dict[str, object] | None = None,
    ) -> dict[str, object]:
        raw_config = read_raw_config(self.settings.config_file)
        transports = _ensure_mapping(raw_config, "transports")
        profile = transports.get(transport_id)
        if not isinstance(profile, dict):
            profile = {}

        resolved_plugin_id = self._resolve_component_plugin_id(
            existing_plugin_id=profile.get("plugin"),
            requested_plugin_id=plugin_id,
            fallback_plugin_id=f"builtin.{transport_id}",
        )
        manifest = self._require_transport_manifest(resolved_plugin_id)
        self._validate_component_updates(
            kind="transport",
            component_id=transport_id,
            allowed_keys=set(manifest.required_config)
            | set(manifest.optional_config)
            | {"plugin", "enabled"},
            updates=config_updates or {},
        )
        self._validate_secret_reference_updates(
            kind="transport",
            component_id=transport_id,
            secret_keys=set(manifest.secret_config),
            updates=config_updates or {},
        )

        profile["plugin"] = resolved_plugin_id
        if enabled is not None:
            profile["enabled"] = enabled
        for key, value in (config_updates or {}).items():
            profile[key] = value
        transports[transport_id] = profile
        write_raw_config(self.settings.config_file, raw_config)
        return {
            "component": "transport",
            "transport_id": transport_id,
            "plugin_id": resolved_plugin_id,
            "enabled": profile.get("enabled", False),
            "config": {str(key): value for key, value in profile.items() if key != "plugin"},
            "required_config": manifest.required_config,
            "optional_config": manifest.optional_config,
            "config_fields": [field_spec.to_dict() for field_spec in manifest.config_fields],
        }

    def configure_tool(
        self,
        tool_id: str,
        *,
        plugin_id: str | None = None,
        enabled: bool | None = None,
        config_updates: dict[str, object] | None = None,
    ) -> dict[str, object]:
        raw_config = read_raw_config(self.settings.config_file)
        tools = _ensure_mapping(raw_config, "tools")
        profile = tools.get(tool_id)
        if not isinstance(profile, dict):
            profile = {}

        resolved_plugin_id = self._resolve_component_plugin_id(
            existing_plugin_id=profile.get("plugin"),
            requested_plugin_id=plugin_id,
            fallback_plugin_id=tool_id.replace("_", "."),
        )
        manifest = self._require_tool_manifest(resolved_plugin_id)
        self._validate_component_updates(
            kind="tool",
            component_id=tool_id,
            allowed_keys=set(manifest.required_config)
            | set(manifest.optional_config)
            | {"plugin", "enabled"},
            updates=config_updates or {},
        )
        self._validate_secret_reference_updates(
            kind="tool",
            component_id=tool_id,
            secret_keys=set(manifest.secret_config),
            updates=config_updates or {},
        )

        profile["plugin"] = resolved_plugin_id
        if enabled is not None:
            profile["enabled"] = enabled
        for key, value in (config_updates or {}).items():
            profile[key] = value
        tools[tool_id] = profile
        write_raw_config(self.settings.config_file, raw_config)
        return {
            "component": "tool",
            "tool_id": tool_id,
            "plugin_id": resolved_plugin_id,
            "enabled": profile.get("enabled", False),
            "config": {str(key): value for key, value in profile.items() if key != "plugin"},
            "required_config": manifest.required_config,
            "optional_config": manifest.optional_config,
            "config_fields": [field_spec.to_dict() for field_spec in manifest.config_fields],
        }

    def configure_workspace(
        self,
        *,
        root: str | None = None,
        mode: str | None = None,
    ) -> dict[str, object]:
        raw_config = read_raw_config(self.settings.config_file)
        workspace = _ensure_mapping(raw_config, "workspace")
        if root is not None:
            workspace["root"] = root
        if mode is not None:
            workspace["mode"] = mode
        write_raw_config(self.settings.config_file, raw_config)
        return {"component": "workspace", "workspace": dict(workspace)}

    def configure_agent(
        self,
        updates: dict[str, object],
    ) -> dict[str, object]:
        allowed_keys = {
            "default_provider",
            "require_provider",
            "system_prompt_file",
            "max_turns",
            "memory",
            "logging",
        }
        self._validate_component_updates(
            kind="agent",
            component_id="agent",
            allowed_keys=allowed_keys,
            updates=updates,
        )
        raw_config = read_raw_config(self.settings.config_file)
        agent = _ensure_mapping(raw_config, "agent")
        for key, value in updates.items():
            if key in {"memory", "logging"} and isinstance(value, dict):
                nested = agent.get(key)
                if not isinstance(nested, dict):
                    nested = {}
                    agent[key] = nested
                nested.update(value)
                continue
            agent[key] = value
        write_raw_config(self.settings.config_file, raw_config)
        return {"component": "agent", "agent": dict(agent)}

    def configure_paths(self, updates: dict[str, object]) -> dict[str, object]:
        allowed_keys = {
            "secrets_file",
            "tool_secrets_file",
            "prompts_dir",
            "plugins_dir",
            "tools_dir",
            "providers_dir",
            "credentials_dir",
        }
        self._validate_component_updates(
            kind="paths",
            component_id="paths",
            allowed_keys=allowed_keys,
            updates=updates,
        )
        raw_config = read_raw_config(self.settings.config_file)
        paths = _ensure_mapping(raw_config, "paths")
        for key, value in updates.items():
            paths[key] = value
        write_raw_config(self.settings.config_file, raw_config)
        return {"component": "paths", "paths": dict(paths)}

    def select_provider_model(
        self,
        provider_id: str,
        *,
        limit: int | None = None,
    ) -> dict[str, object]:
        if self.provider_service is None:
            raise ValueError("Provider service is not available.")
        raw_payload = self.provider_service.list_models(provider_id)
        payload = {str(key): value for key, value in dict(raw_payload).items()}
        models = payload.get("models", [])
        if isinstance(models, list) and limit is not None:
            payload["models"] = models[:limit]
        return payload

    def _require_provider_manifest(self, plugin_id: str) -> Any:
        if self.provider_registry is None:
            raise ValueError("Provider registry is not available.")
        discovery = self.provider_registry.discover(self.settings.providers_dir)
        plugin = discovery.plugins.get(plugin_id)
        if plugin is None:
            raise ValueError(f"Unknown provider plugin {plugin_id!r}.")
        return plugin.manifest

    def _require_transport_manifest(self, plugin_id: str) -> Any:
        if self.transport_registry is None:
            raise ValueError("Transport registry is not available.")
        discovery = self.transport_registry.discover(self.settings.plugins_dir)
        plugin = discovery.plugins.get(plugin_id)
        if plugin is None:
            raise ValueError(f"Unknown transport plugin {plugin_id!r}.")
        return plugin.manifest

    def _require_tool_manifest(self, plugin_id: str) -> Any:
        if self.tool_registry is None:
            raise ValueError("Tool registry is not available.")
        discovery = self.tool_registry.discover(self.settings.tools_dir)
        plugin = discovery.plugins.get(plugin_id)
        if plugin is None:
            raise ValueError(f"Unknown tool plugin {plugin_id!r}.")
        return plugin.manifest

    def _resolve_component_plugin_id(
        self,
        *,
        existing_plugin_id: object,
        requested_plugin_id: str | None,
        fallback_plugin_id: str,
    ) -> str:
        if requested_plugin_id:
            return requested_plugin_id
        if isinstance(existing_plugin_id, str) and existing_plugin_id.strip():
            return existing_plugin_id.strip()
        return fallback_plugin_id

    def _validate_component_updates(
        self,
        *,
        kind: str,
        component_id: str,
        allowed_keys: set[str],
        updates: dict[str, object],
    ) -> None:
        unknown_keys = sorted(set(updates) - allowed_keys)
        if unknown_keys:
            raise ValueError(
                f"{kind.capitalize()} {component_id!r} received unsupported config keys: "
                + ", ".join(repr(key) for key in unknown_keys)
            )

    def _validate_secret_reference_updates(
        self,
        *,
        kind: str,
        component_id: str,
        secret_keys: set[str],
        updates: dict[str, object],
    ) -> None:
        for key in sorted(secret_keys & set(updates)):
            value = updates[key]
            if not isinstance(value, str) or not self._SECRET_NAME_PATTERN.fullmatch(
                value.strip()
            ):
                raise ValueError(
                    f"{kind.capitalize()} {component_id!r} expects {key!r} to be a secret "
                    "name like MY_SECRET, not a raw secret value."
                )
