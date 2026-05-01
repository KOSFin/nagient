from __future__ import annotations

import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

from nagient.app.configuration import TransportInstanceConfig
from nagient.app.settings import Settings
from nagient.infrastructure.runtime import RuntimeAgent
from nagient.plugins.base import BaseTransportPlugin


class _FakePollingTransport(BaseTransportPlugin):
    def __init__(self) -> None:
        self.sent_payloads: list[dict[str, object]] = []

    def normalize_inbound_event(self, payload: object) -> dict[str, object]:
        return {
            "kind": "fake",
            "event_type": "message",
            "text": str(payload),
            "reply_target": {"channel_id": "demo"},
            "payload": {"raw": payload},
        }

    def send_message(self, payload: dict[str, object]) -> dict[str, object]:
        self.sent_payloads.append(dict(payload))
        return {"status": "sent", "payload": dict(payload)}

    def poll_inbound_events(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[object]:
        del transport_id, config, secrets
        return []


class RuntimeAgentTests(unittest.TestCase):
    def test_handle_polled_transport_event_routes_reply_through_generic_payload_contract(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings.from_env({"NAGIENT_HOME": str(Path(temp_dir) / ".nagient")})
            plugin = _FakePollingTransport()
            agent = RuntimeAgent(
                settings=settings,
                inbound_message_handler=lambda transport_id, event: (
                    f"{transport_id}:{event.get('text', '')}"
                ),
            )
            transport = TransportInstanceConfig(
                transport_id="fake",
                plugin_id="custom.fake",
                enabled=True,
                config={},
            )
            log_path = settings.log_dir / "runtime.log"

            agent._handle_polled_transport_event(  # noqa: SLF001
                log_path,
                transport,
                plugin,
                {},
                "hello",
            )

            self.assertEqual(len(plugin.sent_payloads), 1)
            self.assertEqual(plugin.sent_payloads[0]["channel_id"], "demo")
            self.assertEqual(plugin.sent_payloads[0]["text"], "fake:hello")


if __name__ == "__main__":
    unittest.main()
