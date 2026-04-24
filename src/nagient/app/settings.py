from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from nagient.version import __version__


def _expand_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


@dataclass(frozen=True)
class Settings:
    version: str
    home_dir: Path
    config_file: Path
    state_dir: Path
    log_dir: Path
    releases_dir: Path
    channel: str
    update_base_url: str
    heartbeat_interval_seconds: int
    docker_project_name: str

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> Settings:
        env = dict(os.environ if environ is None else environ)
        home_dir = _expand_path(env.get("NAGIENT_HOME", "~/.nagient"))
        config_file = _expand_path(env.get("NAGIENT_CONFIG", str(home_dir / "config.toml")))
        state_dir = _expand_path(env.get("NAGIENT_STATE_DIR", str(home_dir / "state")))
        log_dir = _expand_path(env.get("NAGIENT_LOG_DIR", str(home_dir / "logs")))
        releases_dir = _expand_path(env.get("NAGIENT_RELEASES_DIR", str(home_dir / "releases")))

        file_values = _read_config(config_file)

        return cls(
            version=env.get("NAGIENT_VERSION", __version__),
            home_dir=home_dir,
            config_file=config_file,
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
        )

    def ensure_directories(self) -> None:
        for directory in (
            self.home_dir,
            self.config_file.parent,
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
            "state_dir": str(self.state_dir),
            "log_dir": str(self.log_dir),
            "releases_dir": str(self.releases_dir),
            "channel": self.channel,
            "update_base_url": self.update_base_url,
            "heartbeat_interval_seconds": str(self.heartbeat_interval_seconds),
            "docker_project_name": self.docker_project_name,
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

    values: dict[str, str] = {}
    if isinstance(updates, dict):
        if isinstance(updates.get("channel"), str):
            values["channel"] = str(updates["channel"])
        if isinstance(updates.get("base_url"), str):
            values["update_base_url"] = str(updates["base_url"])
    if isinstance(runtime, dict) and isinstance(runtime.get("heartbeat_interval_seconds"), int):
        values["heartbeat_interval_seconds"] = str(runtime["heartbeat_interval_seconds"])
    if isinstance(docker, dict) and isinstance(docker.get("project_name"), str):
        values["docker_project_name"] = str(docker["project_name"])
    return values
