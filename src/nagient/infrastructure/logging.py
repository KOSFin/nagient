from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from nagient.app.configuration import AgentLoggingConfig, load_runtime_configuration
from nagient.app.settings import Settings


@dataclass(frozen=True)
class LogEvent:
    component: str
    level: str
    event: str
    message: str
    created_at: str
    fields: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "component": self.component,
            "level": self.level,
            "event": self.event,
            "message": self.message,
            "created_at": self.created_at,
            "fields": dict(self.fields),
        }


@dataclass(frozen=True)
class RuntimeLogger:
    settings: Settings
    component: str
    agent_logging: AgentLoggingConfig | None = None

    def bind(self, component: str) -> RuntimeLogger:
        return RuntimeLogger(
            settings=self.settings,
            component=component,
            agent_logging=self.agent_logging,
        )

    def debug(
        self,
        event: str,
        message: str,
        **fields: object,
    ) -> LogEvent:
        return self._write("debug", event, message, fields)

    def info(
        self,
        event: str,
        message: str,
        **fields: object,
    ) -> LogEvent:
        return self._write("info", event, message, fields)

    def warning(
        self,
        event: str,
        message: str,
        **fields: object,
    ) -> LogEvent:
        return self._write("warning", event, message, fields)

    def error(
        self,
        event: str,
        message: str,
        **fields: object,
    ) -> LogEvent:
        return self._write("error", event, message, fields)

    def _write(
        self,
        level: str,
        event: str,
        message: str,
        fields: dict[str, object],
    ) -> LogEvent:
        created_at = _utc_now()
        payload = LogEvent(
            component=self.component,
            level=level,
            event=event,
            message=message,
            created_at=created_at,
            fields=_sanitize_fields(fields),
        )
        logging_config = self._logging_config()
        if not logging_config.log_events or not _should_emit(level, logging_config.level):
            return payload
        self.settings.ensure_directories()
        if logging_config.json_logs:
            events_path = self.settings.log_dir / "events.log"
            with events_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload.to_dict(), ensure_ascii=False) + "\n")
        component_path = self.settings.log_dir / f"{self.component}.log"
        line = f"[{created_at}] {level.upper()} {event}: {message}"
        if payload.fields:
            line += f" {json.dumps(payload.fields, ensure_ascii=False, sort_keys=True)}"
        with component_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        return payload

    def _logging_config(self) -> AgentLoggingConfig:
        fallback = self.agent_logging or AgentLoggingConfig()
        if not self.settings.config_file.exists():
            return fallback
        try:
            return load_runtime_configuration(self.settings).agent.logging
        except Exception:
            return fallback


def _sanitize_fields(fields: dict[str, object]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    for key, value in fields.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            sanitized[str(key)] = value
        elif isinstance(value, Path):
            sanitized[str(key)] = str(value)
        elif isinstance(value, list):
            sanitized[str(key)] = [
                str(item) if isinstance(item, Path) else item
                for item in value
            ]
        elif isinstance(value, dict):
            sanitized[str(key)] = {
                str(inner_key): (
                    str(inner_value) if isinstance(inner_value, Path) else inner_value
                )
                for inner_key, inner_value in value.items()
            }
        else:
            sanitized[str(key)] = str(value)
    return sanitized


def _should_emit(level: str, configured_level: str) -> bool:
    current_rank = _LOG_LEVELS.get(level.lower(), _LOG_LEVELS["info"])
    configured_rank = _LOG_LEVELS.get(configured_level.lower(), _LOG_LEVELS["info"])
    return current_rank >= configured_rank


_LOG_LEVELS = {
    "debug": 10,
    "info": 20,
    "warning": 30,
    "error": 40,
}


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_runtime_log(
    settings: Settings,
    message: str,
    *,
    stream: TextIO | None = None,
) -> str:
    created_at = _utc_now()
    line = f"[nagient] {created_at} {message}"
    print(line, file=stream or sys.stdout, flush=True)
    settings.ensure_directories()
    log_path = settings.log_dir / "runtime.log"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return line
