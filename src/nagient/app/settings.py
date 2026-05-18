from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from nagient.version import __version__


def _expand_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    msg = f"Cannot parse boolean value from {value!r}."
    raise ValueError(msg)


def _path_alias_targets(
    home_dir: Path,
    config_file: Path,
    *,
    include_legacy: bool,
) -> dict[str, Path]:
    aliases = {
        "@home": home_dir.resolve(),
        "@config": config_file.resolve(),
        "@secrets": (home_dir / "secrets.env").resolve(),
        "@tool_secrets": (home_dir / "tool-secrets.env").resolve(),
        "@prompts": (home_dir / "prompts").resolve(),
        "@plugins": (home_dir / "plugins").resolve(),
        "@tools": (home_dir / "tools").resolve(),
        "@providers": (home_dir / "providers").resolve(),
        "@credentials": (home_dir / "credentials").resolve(),
        "@state": (home_dir / "state").resolve(),
        "@logs": (home_dir / "logs").resolve(),
        "@releases": (home_dir / "releases").resolve(),
    }
    if include_legacy:
        aliases["@config_dir"] = config_file.parent.resolve()
    return aliases


def _resolve_path_reference(
    raw_value: str,
    *,
    home_dir: Path,
    config_file: Path,
    fallback: Path,
) -> Path:
    value = raw_value.strip()
    if not value:
        return fallback.resolve()

    aliases = _path_alias_targets(home_dir, config_file, include_legacy=True)
    file_aliases = {"@config", "@secrets", "@tool_secrets"}
    for alias, target in aliases.items():
        if value == alias:
            return target.resolve()
        for separator in ("/", os.sep):
            prefix = f"{alias}{separator}"
            if value.startswith(prefix):
                suffix = value[len(prefix) :]
                base = target.parent if alias in file_aliases else target
                return (base / suffix).expanduser().resolve()

    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = (config_file.parent / candidate).resolve()
    return candidate.resolve()


def _render_path_reference(
    path: str,
    *,
    home_dir: Path,
    config_file: Path,
) -> str:
    resolved = Path(path).expanduser().resolve()
    aliases = _path_alias_targets(home_dir, config_file, include_legacy=False)
    file_aliases = {"@config", "@secrets", "@tool_secrets"}
    for alias, target in aliases.items():
        if resolved == target:
            return alias
    sorted_directory_aliases = sorted(
        [
            (alias, target)
            for alias, target in aliases.items()
            if alias not in file_aliases
        ],
        key=lambda item: len(str(item[1])),
        reverse=True,
    )
    for alias, target in sorted_directory_aliases:
        base = target
        try:
            suffix = resolved.relative_to(base)
        except ValueError:
            continue
        if not suffix.parts:
            return alias
        return f"{alias}/{suffix.as_posix()}"
    return str(resolved)


def _resolve_configured_path(
    env: dict[str, str],
    file_values: dict[str, str],
    *,
    env_key: str,
    file_key: str,
    home_dir: Path,
    config_file: Path,
    default_path: Path,
) -> Path:
    if env_key in env:
        return _resolve_path_reference(
            env[env_key],
            home_dir=home_dir,
            config_file=config_file,
            fallback=default_path,
        )
    if file_key in file_values:
        return _resolve_path_reference(
            file_values[file_key],
            home_dir=home_dir,
            config_file=config_file,
            fallback=default_path,
        )
    return default_path.resolve()


@dataclass(frozen=True)
class Settings:
    version: str
    home_dir: Path
    config_file: Path
    secrets_file: Path
    tool_secrets_file: Path
    prompts_dir: Path
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
        secrets_file = _resolve_configured_path(
            env,
            file_values,
            env_key="NAGIENT_SECRETS_FILE",
            file_key="secrets_file",
            home_dir=home_dir,
            config_file=config_file,
            default_path=home_dir / "secrets.env",
        )
        tool_secrets_file = _resolve_configured_path(
            env,
            file_values,
            env_key="NAGIENT_TOOL_SECRETS_FILE",
            file_key="tool_secrets_file",
            home_dir=home_dir,
            config_file=config_file,
            default_path=home_dir / "tool-secrets.env",
        )
        prompts_dir = _resolve_configured_path(
            env,
            file_values,
            env_key="NAGIENT_PROMPTS_DIR",
            file_key="prompts_dir",
            home_dir=home_dir,
            config_file=config_file,
            default_path=home_dir / "prompts",
        )
        plugins_dir = _resolve_configured_path(
            env,
            file_values,
            env_key="NAGIENT_PLUGINS_DIR",
            file_key="plugins_dir",
            home_dir=home_dir,
            config_file=config_file,
            default_path=home_dir / "plugins",
        )
        tools_dir = _resolve_configured_path(
            env,
            file_values,
            env_key="NAGIENT_TOOLS_DIR",
            file_key="tools_dir",
            home_dir=home_dir,
            config_file=config_file,
            default_path=home_dir / "tools",
        )
        providers_dir = _resolve_configured_path(
            env,
            file_values,
            env_key="NAGIENT_PROVIDERS_DIR",
            file_key="providers_dir",
            home_dir=home_dir,
            config_file=config_file,
            default_path=home_dir / "providers",
        )
        credentials_dir = _resolve_configured_path(
            env,
            file_values,
            env_key="NAGIENT_CREDENTIALS_DIR",
            file_key="credentials_dir",
            home_dir=home_dir,
            config_file=config_file,
            default_path=home_dir / "credentials",
        )
        state_dir = _resolve_configured_path(
            env,
            file_values,
            env_key="NAGIENT_STATE_DIR",
            file_key="state_dir",
            home_dir=home_dir,
            config_file=config_file,
            default_path=home_dir / "state",
        )
        log_dir = _resolve_configured_path(
            env,
            file_values,
            env_key="NAGIENT_LOG_DIR",
            file_key="log_dir",
            home_dir=home_dir,
            config_file=config_file,
            default_path=home_dir / "logs",
        )
        releases_dir = _resolve_configured_path(
            env,
            file_values,
            env_key="NAGIENT_RELEASES_DIR",
            file_key="releases_dir",
            home_dir=home_dir,
            config_file=config_file,
            default_path=home_dir / "releases",
        )

        return cls(
            version=env.get("NAGIENT_VERSION", __version__),
            home_dir=home_dir,
            config_file=config_file,
            secrets_file=secrets_file,
            tool_secrets_file=tool_secrets_file,
            prompts_dir=prompts_dir,
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
            self.prompts_dir,
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
            "prompts_dir": str(self.prompts_dir),
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
        if isinstance(paths.get("prompts_dir"), str):
            values["prompts_dir"] = str(paths["prompts_dir"])
        if isinstance(paths.get("plugins_dir"), str):
            values["plugins_dir"] = str(paths["plugins_dir"])
        if isinstance(paths.get("tools_dir"), str):
            values["tools_dir"] = str(paths["tools_dir"])
        if isinstance(paths.get("providers_dir"), str):
            values["providers_dir"] = str(paths["providers_dir"])
        if isinstance(paths.get("credentials_dir"), str):
            values["credentials_dir"] = str(paths["credentials_dir"])
        if isinstance(paths.get("state_dir"), str):
            values["state_dir"] = str(paths["state_dir"])
        if isinstance(paths.get("log_dir"), str):
            values["log_dir"] = str(paths["log_dir"])
        if isinstance(paths.get("releases_dir"), str):
            values["releases_dir"] = str(paths["releases_dir"])
    return values
