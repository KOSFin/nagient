from __future__ import annotations

import unittest

from nagient.bundled_transports.console.transport import (
    ConsoleTransportPlugin,
)
from nagient.bundled_transports.console.transport import (
    build_plugin as build_console_plugin,
)
from nagient.bundled_transports.telegram.transport import (
    TelegramTransportPlugin,
)
from nagient.bundled_transports.telegram.transport import (
    build_plugin as build_telegram_plugin,
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


class TelegramTransportTests(unittest.TestCase):
    def test_build_plugin_returns_transport(self) -> None:
        plugin = build_telegram_plugin()
        self.assertIsInstance(plugin, TelegramTransportPlugin)
        self.assertIsInstance(plugin, BaseTransportPlugin)

    def test_validate_config_requires_secret_ref(self) -> None:
        plugin = TelegramTransportPlugin()
        issues = plugin.validate_config("telegram", {}, {})
        self.assertTrue(any("missing_secret_ref" in issue.code for issue in issues))

    def test_validate_config_flags_missing_secret(self) -> None:
        plugin = TelegramTransportPlugin()
        issues = plugin.validate_config(
            "telegram",
            {"bot_token_secret": "TELEGRAM_TOKEN"},
            {},
        )
        self.assertTrue(any("secret_not_found" in issue.code for issue in issues))

    def test_validate_config_accepts_valid_settings(self) -> None:
        plugin = TelegramTransportPlugin()
        issues = plugin.validate_config(
            "telegram",
            {"bot_token_secret": "TELEGRAM_TOKEN"},
            {"TELEGRAM_TOKEN": "123456:ABC-DEF"},
        )
        self.assertEqual(issues, [])

    def test_validate_config_rejects_invalid_parse_mode(self) -> None:
        plugin = TelegramTransportPlugin()
        issues = plugin.validate_config(
            "telegram",
            {
                "bot_token_secret": "TELEGRAM_TOKEN",
                "default_parse_mode": "InvalidMode",
            },
            {"TELEGRAM_TOKEN": "123456:ABC-DEF"},
        )
        self.assertTrue(any("invalid_parse_mode" in issue.code for issue in issues))

    def test_normalize_message_event(self) -> None:
        plugin = TelegramTransportPlugin()
        result = plugin.normalize_inbound_event(
            {
                "message": {
                    "message_id": 123,
                    "text": "Hello",
                    "chat": {"id": 456, "type": "private"},
                    "from": {"id": 789, "first_name": "Test"},
                }
            }
        )
        self.assertEqual(result["kind"], "telegram")
        self.assertEqual(result["event_type"], "message")
        self.assertEqual(result["text"], "Hello")
        self.assertEqual(result["session_id"], "telegram:456")

    def test_normalize_command_event(self) -> None:
        plugin = TelegramTransportPlugin()
        result = plugin.normalize_inbound_event(
            {
                "message": {
                    "message_id": 123,
                    "text": "/start",
                    "chat": {"id": 456},
                    "from": {"id": 789},
                }
            }
        )
        self.assertEqual(result["event_type"], "command")
        self.assertEqual(result["command"], "start")

    def test_self_test_rejects_invalid_token_format(self) -> None:
        plugin = TelegramTransportPlugin()
        issues = plugin.self_test(
            "telegram",
            {"bot_token_secret": "TELEGRAM_TOKEN"},
            {"TELEGRAM_TOKEN": "invalid-token"},
        )
        self.assertTrue(any("invalid_token_format" in issue.code for issue in issues))

    def test_self_test_accepts_valid_token_format(self) -> None:
        plugin = TelegramTransportPlugin()
        issues = plugin.self_test(
            "telegram",
            {"bot_token_secret": "TELEGRAM_TOKEN"},
            {"TELEGRAM_TOKEN": "123456:ABC-DEF"},
        )
        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
