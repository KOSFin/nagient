from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nagient.app.settings import Settings


@dataclass(frozen=True)
class TransportInstanceConfig:
    transport_id: str
    plugin_id: str
    enabled: bool
    config: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "transport_id": self.transport_id,
            "plugin_id": self.plugin_id,
            "enabled": self.enabled,
            "config": dict(self.config),
        }


@dataclass(frozen=True)
class ProviderInstanceConfig:
    provider_id: str
    plugin_id: str
    enabled: bool
    config: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "plugin_id": self.plugin_id,
            "enabled": self.enabled,
            "config": dict(self.config),
        }


@dataclass(frozen=True)
class RuntimeConfiguration:
    settings: Settings
    safe_mode: bool
    default_provider: str | None
    require_provider: bool
    transports: list[TransportInstanceConfig]
    providers: list[ProviderInstanceConfig]
    secrets: dict[str, str] = field(default_factory=dict)
    raw_config: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "settings": self.settings.to_dict(),
            "safe_mode": self.safe_mode,
            "default_provider": self.default_provider,
            "require_provider": self.require_provider,
            "secret_keys": sorted(self.secrets),
            "transports": [transport.to_dict() for transport in self.transports],
            "providers": [provider.to_dict() for provider in self.providers],
        }


def load_runtime_configuration(
    settings: Settings,
    environ: dict[str, str] | None = None,
) -> RuntimeConfiguration:
    env = dict(os.environ if environ is None else environ)
    raw_config = merge_runtime_config(read_raw_config(settings.config_file), env)
    transports = _parse_transports(raw_config)
    if not transports:
        transports = [
            TransportInstanceConfig(
                transport_id="console",
                plugin_id="builtin.console",
                enabled=True,
                config={},
            )
        ]
    providers = _parse_providers(raw_config)

    return RuntimeConfiguration(
        settings=settings,
        safe_mode=settings.safe_mode,
        default_provider=_parse_default_provider(raw_config),
        require_provider=_parse_require_provider(raw_config),
        transports=transports,
        providers=providers,
        secrets=load_secrets(settings.secrets_file),
        raw_config=raw_config,
    )


def read_raw_config(config_file: Path) -> dict[str, object]:
    if not config_file.exists():
        return {}

    payload = tomllib.loads(config_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    return {str(key): value for key, value in payload.items()}


def load_secrets(secrets_file: Path) -> dict[str, str]:
    if not secrets_file.exists():
        return {}

    secrets: dict[str, str] = {}
    for raw_line in secrets_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_value = value.strip()
        if (
            len(normalized_value) >= 2
            and normalized_value[0] == normalized_value[-1]
            and normalized_value[0] in {'"', "'"}
        ):
            normalized_value = normalized_value[1:-1]
        secrets[key.strip()] = normalized_value
    return secrets


def render_default_config(settings: Settings) -> str:
    return "\n".join(
        [
            "[updates]",
            f'channel = "{settings.channel}"',
            f'base_url = "{settings.update_base_url}"',
            "",
            "[runtime]",
            f"heartbeat_interval_seconds = {settings.heartbeat_interval_seconds}",
            f"safe_mode = {str(settings.safe_mode).lower()}",
            "",
            "[docker]",
            f'project_name = "{settings.docker_project_name}"',
            "",
            "[paths]",
            f'secrets_file = "{settings.secrets_file}"',
            f'plugins_dir = "{settings.plugins_dir}"',
            f'providers_dir = "{settings.providers_dir}"',
            f'credentials_dir = "{settings.credentials_dir}"',
            "",
            "[agent]",
            'default_provider = ""',
            "require_provider = false",
            "",
            "[transports.console]",
            'plugin = "builtin.console"',
            "enabled = true",
            "",
            "[transports.webhook]",
            'plugin = "builtin.webhook"',
            "enabled = false",
            'listen_host = "0.0.0.0"',
            "listen_port = 8080",
            'path = "/events"',
            'shared_secret_name = "NAGIENT_WEBHOOK_SHARED_SECRET"',
            "",
            "[transports.telegram]",
            'plugin = "builtin.telegram"',
            "enabled = false",
            'bot_token_secret = "TELEGRAM_BOT_TOKEN"',
            'default_chat_id = ""',
            "",
            "[providers.openai]",
            'plugin = "builtin.openai"',
            "enabled = false",
            'auth = "api_key"',
            'api_key_secret = "OPENAI_API_KEY"',
            'model = "gpt-4.1-mini"',
            "",
            "[providers.anthropic]",
            'plugin = "builtin.anthropic"',
            "enabled = false",
            'auth = "api_key"',
            'api_key_secret = "ANTHROPIC_API_KEY"',
            'model = "claude-sonnet-4-5"',
            "",
            "[providers.gemini]",
            'plugin = "builtin.gemini"',
            "enabled = false",
            'auth = "api_key"',
            'api_key_secret = "GEMINI_API_KEY"',
            'model = "gemini-2.5-pro"',
            "",
            "[providers.deepseek]",
            'plugin = "builtin.deepseek"',
            "enabled = false",
            'auth = "api_key"',
            'api_key_secret = "DEEPSEEK_API_KEY"',
            'model = "deepseek-chat"',
            "",
            "[providers.ollama]",
            'plugin = "builtin.ollama"',
            "enabled = false",
            'auth = "none"',
            'base_url = "http://127.0.0.1:11434"',
            'model = "llama3.1:8b"',
            "",
        ]
    ) + "\n"


def render_default_secrets() -> str:
    return "\n".join(
        [
            "# Fill only the secrets you actually use.",
            "# OPENAI_API_KEY=",
            "# ANTHROPIC_API_KEY=",
            "# GEMINI_API_KEY=",
            "# DEEPSEEK_API_KEY=",
            "# TELEGRAM_BOT_TOKEN=",
            "# NAGIENT_WEBHOOK_SHARED_SECRET=",
            "",
        ]
    )


def render_plugins_readme() -> str:
    return "\n".join(
        [
            "# Nagient custom transport plugins",
            "",
            "Each plugin lives in its own directory and must contain at least:",
            "- `plugin.toml`",
            "- `transport.py`",
            "- `instructions.md`",
            "- `schema.json`",
            "",
            "Generate a new template with:",
            "",
            "```bash",
            "nagient transport scaffold --plugin-id your.plugin.id",
            "```",
            "",
        ]
    )


def render_providers_readme() -> str:
    return "\n".join(
        [
            "# Nagient custom provider plugins",
            "",
            "Each provider lives in its own directory and must contain at least:",
            "- `provider.toml`",
            "- `provider.py`",
            "- `schema.json`",
            "",
            "Generate a new template with:",
            "",
            "```bash",
            "nagient provider scaffold --plugin-id your.provider.id",
            "```",
            "",
        ]
    )


def render_credentials_readme() -> str:
    return "\n".join(
        [
            "# Nagient credentials store",
            "",
            "This directory stores OAuth/device-login tokens and other non-env credentials.",
            "Files are managed by Nagient and should not be committed to source control.",
            "",
        ]
    )


def activation_report_path(settings: Settings) -> Path:
    return settings.state_dir / "activation-report.json"


def effective_config_path(settings: Settings) -> Path:
    return settings.state_dir / "effective-config.json"


def last_known_good_path(settings: Settings) -> Path:
    return settings.state_dir / "last-known-good.json"


def auth_sessions_dir(settings: Settings) -> Path:
    return settings.state_dir / "auth-sessions"


def _parse_transports(payload: dict[str, object]) -> list[TransportInstanceConfig]:
    raw_transports = payload.get("transports")
    if not isinstance(raw_transports, dict):
        return []

    transports: list[TransportInstanceConfig] = []
    for transport_id, values in raw_transports.items():
        if not isinstance(transport_id, str) or not isinstance(values, dict):
            continue
        plugin_id = values.get("plugin", f"builtin.{transport_id}")
        if not isinstance(plugin_id, str):
            plugin_id = str(plugin_id)
        enabled = _coerce_bool(values.get("enabled", True))
        transport_config = {
            str(key): value
            for key, value in values.items()
            if key not in {"plugin", "enabled"}
        }
        transports.append(
            TransportInstanceConfig(
                transport_id=transport_id,
                plugin_id=plugin_id,
                enabled=enabled,
                config=transport_config,
            )
        )
    return transports


def _parse_providers(payload: dict[str, object]) -> list[ProviderInstanceConfig]:
    raw_providers = payload.get("providers")
    if not isinstance(raw_providers, dict):
        return []

    providers: list[ProviderInstanceConfig] = []
    for provider_id, values in raw_providers.items():
        if not isinstance(provider_id, str) or not isinstance(values, dict):
            continue
        plugin_id = values.get("plugin", f"builtin.{provider_id}")
        if not isinstance(plugin_id, str):
            plugin_id = str(plugin_id)
        enabled = _coerce_bool(values.get("enabled", False))
        provider_config = {
            str(key): value
            for key, value in values.items()
            if key not in {"plugin", "enabled"}
        }
        providers.append(
            ProviderInstanceConfig(
                provider_id=provider_id,
                plugin_id=plugin_id,
                enabled=enabled,
                config=provider_config,
            )
        )
    return providers


def _parse_default_provider(payload: dict[str, object]) -> str | None:
    agent = payload.get("agent")
    if not isinstance(agent, dict):
        return None
    default_provider = agent.get("default_provider")
    if isinstance(default_provider, str) and default_provider.strip():
        return default_provider.strip()
    return None


def _parse_require_provider(payload: dict[str, object]) -> bool:
    agent = payload.get("agent")
    if not isinstance(agent, dict):
        return False
    return _coerce_bool(agent.get("require_provider", False))


def merge_runtime_config(
    payload: dict[str, object],
    environ: dict[str, str],
) -> dict[str, object]:
    merged: dict[str, object] = dict(payload)
    providers = merged.get("providers")
    if not isinstance(providers, dict):
        providers = {}
    providers = {
        str(provider_id): dict(values) if isinstance(values, dict) else {}
        for provider_id, values in providers.items()
    }

    for key, value in environ.items():
        if key == "NAGIENT_AGENT_DEFAULT_PROVIDER":
            agent = _ensure_mapping(merged, "agent")
            agent["default_provider"] = value
            continue
        if key == "NAGIENT_AGENT_REQUIRE_PROVIDER":
            agent = _ensure_mapping(merged, "agent")
            agent["require_provider"] = _coerce_env_value(value)
            continue
        if not key.startswith("NAGIENT_PROVIDER__"):
            continue
        parts = key.split("__")
        if len(parts) < 3:
            continue
        provider_id = parts[1].strip().lower()
        field_name = "__".join(parts[2:]).strip().lower()
        if not provider_id or not field_name:
            continue
        provider_values = providers.get(provider_id, {})
        provider_values[field_name] = _coerce_env_value(value)
        providers[provider_id] = provider_values

    if providers:
        merged["providers"] = providers
    return merged


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _coerce_env_value(value: str) -> Any:
    normalized = value.strip()
    lowered = normalized.lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    if normalized.isdigit():
        return int(normalized)
    return value


def _ensure_mapping(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    if isinstance(value, dict):
        return value
    created: dict[str, object] = {}
    payload[key] = created
    return created
