from __future__ import annotations

import unittest

from nagient.bundled_transports.console.transport import (
    ConsoleTransportPlugin,
)
from nagient.bundled_transports.console.transport import (
    build_plugin as build_console_plugin,
)
from nagient.bundled_transports.webhook.transport import (
    WebhookTransportPlugin,
)
from nagient.bundled_transports.webhook.transport import (
    build_plugin as build_webhook_plugin,
)
from nagient.plugins.base import BaseTransportPlugin


class ConsoleTransportTests(unittest.TestCase):
    def test_build_plugin_returns_transport(self) -> None:
        plugin = build_console_plugin()
        self.assertIsInstance(plugin, ConsoleTransportPlugin)
        self.assertIsInstance(plugin, BaseTransportPlugin)

    def test_validate_config_accepts_valid_stream(self) -> None:
        plugin = ConsoleTransportPlugin()
        issues = plugin.validate_config("console", {"stream": "stdout"}, {})
        self.assertEqual(issues, [])

    def test_validate_config_rejects_invalid_stream(self) -> None:
        plugin = ConsoleTransportPlugin()
        issues = plugin.validate_config("console", {"stream": "invalid"}, {})
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "error")
        self.assertIn("invalid_stream", issues[0].code)

    def test_send_message_queues_payload(self) -> None:
        plugin = ConsoleTransportPlugin()
        result = plugin.send_message({"text": "Hello, world!"})
        self.assertEqual(result["status"], "queued")
        self.assertIn("payload", result)

    def test_normalize_inbound_event(self) -> None:
        plugin = ConsoleTransportPlugin()
        result = plugin.normalize_inbound_event({"test": "data"})
        self.assertEqual(result["kind"], "console")
        self.assertEqual(result["event_type"], "unknown")


class WebhookTransportTests(unittest.TestCase):
    def test_build_plugin_returns_transport(self) -> None:
        plugin = build_webhook_plugin()
        self.assertIsInstance(plugin, WebhookTransportPlugin)
        self.assertIsInstance(plugin, BaseTransportPlugin)

    def test_validate_config_accepts_valid_settings(self) -> None:
        plugin = WebhookTransportPlugin()
        issues = plugin.validate_config(
            "webhook",
            {
                "path": "/webhook",
                "listen_port": 8080,
                "shared_secret_name": "WEBHOOK_SECRET",
            },
            {"WEBHOOK_SECRET": "test-secret"},
        )
        self.assertEqual(issues, [])

    def test_validate_config_rejects_invalid_path(self) -> None:
        plugin = WebhookTransportPlugin()
        issues = plugin.validate_config("webhook", {"path": "invalid-path"}, {})
        self.assertTrue(any("invalid_path" in issue.code for issue in issues))

    def test_validate_config_flags_missing_secret(self) -> None:
        plugin = WebhookTransportPlugin()
        issues = plugin.validate_config(
            "webhook",
            {"path": "/webhook", "shared_secret_name": "MISSING_SECRET"},
            {},
        )
        self.assertTrue(any("missing_secret" in issue.code for issue in issues))

    def test_normalize_inbound_event_dict(self) -> None:
        plugin = WebhookTransportPlugin()
        result = plugin.normalize_inbound_event(
            {
                "event_type": "message",
                "text": "Hello",
                "session_id": "test-session",
            }
        )
        self.assertEqual(result["kind"], "webhook")
        self.assertEqual(result["event_type"], "message")
        self.assertEqual(result["text"], "Hello")




if __name__ == "__main__":
    unittest.main()
