from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from nagient.domain.entities.config_fields import ConfigFieldSpec
from nagient.domain.entities.system_state import CheckIssue

REQUIRED_TRANSPORT_SLOTS = (
    "send_message",
    "send_notification",
    "normalize_inbound_event",
    "poll_inbound_events",
    "healthcheck",
    "selftest",
    "start",
    "stop",
)


@dataclass(frozen=True)
class TransportPluginManifest:
    plugin_id: str
    display_name: str
    version: str
    namespace: str
    entrypoint: str
    required_slots: dict[str, str]
    function_bindings: dict[str, str]
    custom_functions: list[str] = field(default_factory=list)
    required_config: list[str] = field(default_factory=list)
    optional_config: list[str] = field(default_factory=list)
    secret_config: list[str] = field(default_factory=list)
    config_fields: list[ConfigFieldSpec] = field(default_factory=list)
    instruction_template: str = ""
    config_schema_file: str | None = None

    @property
    def exposed_functions(self) -> list[str]:
        return sorted(self.function_bindings)

    @property
    def allowed_config(self) -> set[str]:
        return set(self.required_config) | set(self.optional_config)

    def field_by_key(self, key: str) -> ConfigFieldSpec | None:
        for field_spec in self.config_fields:
            if field_spec.key == key:
                return field_spec
        return None


@dataclass(frozen=True)
class LoadedTransportPlugin:
    manifest: TransportPluginManifest
    implementation: BaseTransportPlugin
    source: str


@dataclass(frozen=True)
class TransportRuntimeContext:
    state_dir: Path
    log: Callable[[str], None]


class BaseTransportPlugin:
    manifest: TransportPluginManifest

    def validate_config(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        return []

    def self_test(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        return []

    def healthcheck(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        return []

    def bind_runtime(
        self,
        transport_id: str,
        runtime: TransportRuntimeContext,
    ) -> None:
        del transport_id, runtime
        return None

    def send_message(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "queued", "payload": payload}

    def send_notification(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "queued", "payload": payload}

    def normalize_inbound_event(self, payload: object) -> dict[str, object]:
        return {"event_type": "unknown", "payload": payload}

    def poll_inbound_events(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[object]:
        del transport_id, config, secrets
        return []

    def start(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> None:
        return None

    def stop(self, transport_id: str) -> None:
        return None
