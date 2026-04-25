from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

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
class RuntimeConfiguration:
    settings: Settings
    safe_mode: bool
    transports: list[TransportInstanceConfig]
    secrets: dict[str, str] = field(default_factory=dict)
    raw_config: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "settings": self.settings.to_dict(),
            "safe_mode": self.safe_mode,
            "secret_keys": sorted(self.secrets),
            "transports": [transport.to_dict() for transport in self.transports],
        }


def load_runtime_configuration(settings: Settings) -> RuntimeConfiguration:
    raw_config = read_raw_config(settings.config_file)
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

    return RuntimeConfiguration(
        settings=settings,
        safe_mode=settings.safe_mode,
        transports=transports,
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
        ]
    ) + "\n"


def render_default_secrets() -> str:
    return "\n".join(
        [
            "# Fill only the secrets you actually use.",
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


def activation_report_path(settings: Settings) -> Path:
    return settings.state_dir / "activation-report.json"


def effective_config_path(settings: Settings) -> Path:
    return settings.state_dir / "effective-config.json"


def last_known_good_path(settings: Settings) -> Path:
    return settings.state_dir / "last-known-good.json"


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
