from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from nagient.app.settings import Settings
from nagient.application.services.transport_router_service import TransportRouterService
from nagient.infrastructure.logging import RuntimeLogger
from nagient.plugins.base import LoadedTransportPlugin, TransportPluginManifest


class _FakeTransportImplementation:
    def __init__(self) -> None:
        self.sent_payloads: list[dict[str, object]] = []
        self.typing_payloads: list[dict[str, object]] = []

    def send_message(self, payload: dict[str, object]) -> dict[str, object]:
        self.sent_payloads.append(dict(payload))
        return {"status": "sent", "payload": dict(payload)}

    def send_typing(self, payload: dict[str, object]) -> dict[str, object]:
        self.typing_payloads.append(dict(payload))
        return {"status": "typing", "payload": dict(payload)}


class _FakePluginRegistry:
    def __init__(self, plugin: LoadedTransportPlugin) -> None:
        self._plugin = plugin

    def discover(self, plugins_dir: Path) -> SimpleNamespace:
        del plugins_dir
        return SimpleNamespace(plugins={"custom.demo": self._plugin}, issues=[])


class TransportRouterServiceTests(unittest.TestCase):
    def test_router_injects_runtime_transport_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            settings.ensure_directories()
            settings.config_file.write_text(
                "\n".join(
                    [
                        "[transports.demo]",
                        'plugin = "custom.demo"',
                        "enabled = true",
                        'channel = "primary"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            implementation = _FakeTransportImplementation()
            plugin = LoadedTransportPlugin(
                manifest=TransportPluginManifest(
                    plugin_id="custom.demo",
                    display_name="Demo Transport",
                    version="0.1.0",
                    namespace="demo",
                    entrypoint="demo.py",
                    required_slots={
                        "send_message": "demo.sendMessage",
                        "send_notification": "demo.sendNotification",
                        "normalize_inbound_event": "demo.normalizeInboundEvent",
                        "poll_inbound_events": "demo.pollInboundEvents",
                        "healthcheck": "demo.healthcheck",
                        "selftest": "demo.selftest",
                        "start": "demo.start",
                        "stop": "demo.stop",
                    },
                    function_bindings={
                        "demo.sendMessage": "send_message",
                        "demo.sendTyping": "send_typing",
                    },
                ),
                implementation=implementation,
                source="test",
            )
            service = TransportRouterService(
                settings=settings,
                plugin_registry=_FakePluginRegistry(plugin),
                logger=RuntimeLogger(settings, "router-test"),
            )

            service.send_message(
                transport_id="demo",
                payload={"text": "hello", "channel_id": "123"},
            )

            self.assertEqual(len(implementation.sent_payloads), 1)
            self.assertEqual(
                implementation.sent_payloads[0]["_transport_config"]["channel"],
                "primary",
            )

    def test_router_uses_explicit_typing_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            settings.ensure_directories()
            settings.config_file.write_text(
                "\n".join(
                    [
                        "[transports.demo]",
                        'plugin = "custom.demo"',
                        "enabled = true",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            implementation = _FakeTransportImplementation()
            plugin = LoadedTransportPlugin(
                manifest=TransportPluginManifest(
                    plugin_id="custom.demo",
                    display_name="Demo Transport",
                    version="0.1.0",
                    namespace="demo",
                    entrypoint="demo.py",
                    required_slots={
                        "send_message": "demo.sendMessage",
                        "send_notification": "demo.sendNotification",
                        "normalize_inbound_event": "demo.normalizeInboundEvent",
                        "poll_inbound_events": "demo.pollInboundEvents",
                        "healthcheck": "demo.healthcheck",
                        "selftest": "demo.selftest",
                        "start": "demo.start",
                        "stop": "demo.stop",
                    },
                    function_bindings={
                        "demo.sendMessage": "send_message",
                        "demo.sendTyping": "send_typing",
                    },
                ),
                implementation=implementation,
                source="test",
            )
            service = TransportRouterService(
                settings=settings,
                plugin_registry=_FakePluginRegistry(plugin),
                logger=RuntimeLogger(settings, "router-test"),
            )

            payload = service.send_typing(
                transport_id="demo",
                payload={"channel_id": "123"},
            )

            self.assertEqual(payload["status"], "typing")
            self.assertEqual(len(implementation.typing_payloads), 1)


if __name__ == "__main__":
    unittest.main()
