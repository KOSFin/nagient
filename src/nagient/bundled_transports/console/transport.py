from __future__ import annotations

from collections.abc import Mapping

from nagient.domain.entities.system_state import CheckIssue
from nagient.plugins.base import BaseTransportPlugin


class ConsoleTransportPlugin(BaseTransportPlugin):
    """Console transport for direct terminal interaction."""

    def validate_config(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        del secrets
        stream = config.get("stream", "stdout")
        if stream not in {"stdout", "stderr"}:
            return [
                CheckIssue(
                    severity="error",
                    code="transport.console.invalid_stream",
                    message=f"Transport {transport_id!r} must use stream stdout or stderr.",
                    source=transport_id,
                )
            ]
        return []

    def send_message(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "queued", "payload": payload}

    def send_notification(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "queued", "payload": payload}

    def normalize_inbound_event(self, payload: object) -> dict[str, object]:
        return {"kind": "console", "event_type": "unknown", "payload": payload}

    def self_test(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        del transport_id, config, secrets
        return []

    def render_notice(self, text: str) -> dict[str, object]:
        return {"status": "rendered", "text": text}


def build_plugin() -> ConsoleTransportPlugin:
    return ConsoleTransportPlugin()
