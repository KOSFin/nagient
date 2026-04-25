from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from nagient.domain.entities.system_state import CheckIssue

REQUIRED_TRANSPORT_SLOTS = (
    "send_message",
    "send_notification",
    "normalize_inbound_event",
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
    instruction_template: str = ""
    config_schema_file: str | None = None

    @property
    def exposed_functions(self) -> list[str]:
        return sorted(self.function_bindings)

    @property
    def allowed_config(self) -> set[str]:
        return set(self.required_config) | set(self.optional_config)


@dataclass(frozen=True)
class LoadedTransportPlugin:
    manifest: TransportPluginManifest
    implementation: object
    source: str


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

    def start(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> None:
        return None

    def stop(self, transport_id: str) -> None:
        return None
