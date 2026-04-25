from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from nagient.version import __version__


def _expand_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _expand_config_relative_path(value: str, base_dir: Path) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = (base_dir / candidate).resolve()
    return candidate.resolve()


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    msg = f"Cannot parse boolean value from {value!r}."
    raise ValueError(msg)


@dataclass(frozen=True)
class Settings:
    version: str
    home_dir: Path
    config_file: Path
    secrets_file: Path
    tool_secrets_file: Path
    plugins_dir: Path
    providers_dir: Path
    tools_dir: Path
    credentials_dir: Path
    state_dir: Path
    log_dir: Path
    releases_dir: Path
    channel: str
    update_base_url: str
    heartbeat_interval_seconds: int
    docker_project_name: str
    safe_mode: bool

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> Settings:
        env = dict(os.environ if environ is None else environ)
        home_dir = _expand_path(env.get("NAGIENT_HOME", "~/.nagient"))
        config_file = _expand_path(env.get("NAGIENT_CONFIG", str(home_dir / "config.toml")))
        file_values = _read_config(config_file)
        if "NAGIENT_SECRETS_FILE" in env:
            secrets_file = _expand_path(env["NAGIENT_SECRETS_FILE"])
        elif "secrets_file" in file_values:
            secrets_file = _expand_config_relative_path(
                file_values["secrets_file"],
                config_file.parent,
            )
        else:
            secrets_file = _expand_path(str(home_dir / "secrets.env"))

        if "NAGIENT_PLUGINS_DIR" in env:
            plugins_dir = _expand_path(env["NAGIENT_PLUGINS_DIR"])
        elif "plugins_dir" in file_values:
            plugins_dir = _expand_config_relative_path(
                file_values["plugins_dir"],
                config_file.parent,
            )
        else:
            plugins_dir = _expand_path(str(home_dir / "plugins"))
        if "NAGIENT_TOOLS_DIR" in env:
            tools_dir = _expand_path(env["NAGIENT_TOOLS_DIR"])
        elif "tools_dir" in file_values:
            tools_dir = _expand_config_relative_path(
                file_values["tools_dir"],
                config_file.parent,
            )
        else:
            tools_dir = _expand_path(str(home_dir / "tools"))
        if "NAGIENT_PROVIDERS_DIR" in env:
            providers_dir = _expand_path(env["NAGIENT_PROVIDERS_DIR"])
        elif "providers_dir" in file_values:
            providers_dir = _expand_config_relative_path(
                file_values["providers_dir"],
                config_file.parent,
            )
        else:
            providers_dir = _expand_path(str(home_dir / "providers"))
        if "NAGIENT_CREDENTIALS_DIR" in env:
            credentials_dir = _expand_path(env["NAGIENT_CREDENTIALS_DIR"])
        elif "credentials_dir" in file_values:
            credentials_dir = _expand_config_relative_path(
                file_values["credentials_dir"],
                config_file.parent,
            )
        else:
            credentials_dir = _expand_path(str(home_dir / "credentials"))
        if "NAGIENT_TOOL_SECRETS_FILE" in env:
            tool_secrets_file = _expand_path(env["NAGIENT_TOOL_SECRETS_FILE"])
        elif "tool_secrets_file" in file_values:
            tool_secrets_file = _expand_config_relative_path(
                file_values["tool_secrets_file"],
                config_file.parent,
            )
        else:
            tool_secrets_file = _expand_path(str(home_dir / "tool-secrets.env"))
        state_dir = _expand_path(env.get("NAGIENT_STATE_DIR", str(home_dir / "state")))
        log_dir = _expand_path(env.get("NAGIENT_LOG_DIR", str(home_dir / "logs")))
        releases_dir = _expand_path(env.get("NAGIENT_RELEASES_DIR", str(home_dir / "releases")))

        return cls(
            version=env.get("NAGIENT_VERSION", __version__),
            home_dir=home_dir,
            config_file=config_file,
            secrets_file=secrets_file,
            tool_secrets_file=tool_secrets_file,
            plugins_dir=plugins_dir,
            providers_dir=providers_dir,
            tools_dir=tools_dir,
            credentials_dir=credentials_dir,
            state_dir=state_dir,
            log_dir=log_dir,
            releases_dir=releases_dir,
            channel=env.get("NAGIENT_CHANNEL", file_values.get("channel", "stable")),
            update_base_url=env.get(
                "NAGIENT_UPDATE_BASE_URL",
                file_values.get("update_base_url", ""),
            ),
            heartbeat_interval_seconds=int(
                env.get(
                    "NAGIENT_HEARTBEAT_INTERVAL",
                    file_values.get("heartbeat_interval_seconds", "30"),
                )
            ),
            docker_project_name=env.get(
                "NAGIENT_DOCKER_PROJECT_NAME",
                file_values.get("docker_project_name", "nagient"),
            ),
            safe_mode=_parse_bool(
                env.get(
                    "NAGIENT_SAFE_MODE",
                    file_values.get("safe_mode", "true"),
                )
            ),
        )

    def ensure_directories(self) -> None:
        for directory in (
            self.home_dir,
            self.config_file.parent,
            self.secrets_file.parent,
            self.tool_secrets_file.parent,
            self.plugins_dir,
            self.providers_dir,
            self.tools_dir,
            self.credentials_dir,
            self.state_dir,
            self.log_dir,
            self.releases_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict[str, str]:
        return {
            "version": self.version,
            "home_dir": str(self.home_dir),
            "config_file": str(self.config_file),
            "secrets_file": str(self.secrets_file),
            "tool_secrets_file": str(self.tool_secrets_file),
            "plugins_dir": str(self.plugins_dir),
            "providers_dir": str(self.providers_dir),
            "tools_dir": str(self.tools_dir),
            "credentials_dir": str(self.credentials_dir),
            "state_dir": str(self.state_dir),
            "log_dir": str(self.log_dir),
            "releases_dir": str(self.releases_dir),
            "channel": self.channel,
            "update_base_url": self.update_base_url,
            "heartbeat_interval_seconds": str(self.heartbeat_interval_seconds),
            "docker_project_name": self.docker_project_name,
            "safe_mode": str(self.safe_mode).lower(),
        }


def _read_config(config_file: Path) -> dict[str, str]:
    if not config_file.exists():
        return {}

    payload = tomllib.loads(config_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}

    runtime = payload.get("runtime", {})
    updates = payload.get("updates", {})
    docker = payload.get("docker", {})
    paths = payload.get("paths", {})

    values: dict[str, str] = {}
    if isinstance(updates, dict):
        if isinstance(updates.get("channel"), str):
            values["channel"] = str(updates["channel"])
        if isinstance(updates.get("base_url"), str):
            values["update_base_url"] = str(updates["base_url"])
    if isinstance(runtime, dict):
        if isinstance(runtime.get("heartbeat_interval_seconds"), int):
            values["heartbeat_interval_seconds"] = str(runtime["heartbeat_interval_seconds"])
        if isinstance(runtime.get("safe_mode"), bool):
            values["safe_mode"] = str(runtime["safe_mode"]).lower()
    if isinstance(docker, dict) and isinstance(docker.get("project_name"), str):
        values["docker_project_name"] = str(docker["project_name"])
    if isinstance(paths, dict):
        if isinstance(paths.get("secrets_file"), str):
            values["secrets_file"] = str(paths["secrets_file"])
        if isinstance(paths.get("tool_secrets_file"), str):
            values["tool_secrets_file"] = str(paths["tool_secrets_file"])
        if isinstance(paths.get("plugins_dir"), str):
            values["plugins_dir"] = str(paths["plugins_dir"])
        if isinstance(paths.get("tools_dir"), str):
            values["tools_dir"] = str(paths["tools_dir"])
        if isinstance(paths.get("providers_dir"), str):
            values["providers_dir"] = str(paths["providers_dir"])
        if isinstance(paths.get("credentials_dir"), str):
            values["credentials_dir"] = str(paths["credentials_dir"])
    return values
