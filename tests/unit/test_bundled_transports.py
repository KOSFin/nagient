"""
Unit tests for bundled transport plugins.
"""

from __future__ import annotations

from nagient.bundled_transports.console.transport import ConsoleTransportPlugin
from nagient.bundled_transports.telegram.transport import TelegramTransportPlugin
from nagient.bundled_transports.webhook.transport import WebhookTransportPlugin
from nagient.plugins.base import BaseTransportPlugin


class TestConsoleTransport:
    """Test console transport plugin."""

    def test_build_plugin(self):
        """Test plugin factory function."""
        from nagient.bundled_transports.console.transport import build_plugin

        plugin = build_plugin()
        assert isinstance(plugin, ConsoleTransportPlugin)
        assert isinstance(plugin, BaseTransportPlugin)

    def test_validate_config_valid(self):
        """Test config validation with valid stream."""
        plugin = ConsoleTransportPlugin()
        issues = plugin.validate_config(
            "test_console",
            {"stream": "stdout"},
            {},
        )
        assert len(issues) == 0

    def test_validate_config_invalid_stream(self):
        """Test config validation with invalid stream."""
        plugin = ConsoleTransportPlugin()
        issues = plugin.validate_config(
            "test_console",
            {"stream": "invalid"},
            {},
        )
        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert "invalid_stream" in issues[0].code

    def test_send_message(self):
        """Test sending a message."""
        plugin = ConsoleTransportPlugin()
        result = plugin.send_message({"text": "Hello, world!"})
        assert result["status"] == "queued"
        assert "payload" in result

    def test_normalize_inbound_event(self):
        """Test event normalization."""
        plugin = ConsoleTransportPlugin()
        result = plugin.normalize_inbound_event({"test": "data"})
        assert result["kind"] == "console"
        assert result["event_type"] == "unknown"


class TestWebhookTransport:
    """Test webhook transport plugin."""

    def test_build_plugin(self):
        """Test plugin factory function."""
        from nagient.bundled_transports.webhook.transport import build_plugin

        plugin = build_plugin()
        assert isinstance(plugin, WebhookTransportPlugin)
        assert isinstance(plugin, BaseTransportPlugin)

    def test_validate_config_valid(self):
        """Test config validation with valid settings."""
        plugin = WebhookTransportPlugin()
        issues = plugin.validate_config(
            "test_webhook",
            {
                "path": "/webhook",
                "listen_port": 8080,
                "shared_secret_name": "WEBHOOK_SECRET",
            },
            {"WEBHOOK_SECRET": "test-secret"},
        )
        assert len(issues) == 0

    def test_validate_config_invalid_path(self):
        """Test config validation with invalid path."""
        plugin = WebhookTransportPlugin()
        issues = plugin.validate_config(
            "test_webhook",
            {"path": "invalid-path"},
            {},
        )
        assert len(issues) > 0
        assert any("invalid_path" in issue.code for issue in issues)

    def test_validate_config_missing_secret(self):
        """Test config validation with missing secret."""
        plugin = WebhookTransportPlugin()
        issues = plugin.validate_config(
            "test_webhook",
            {
                "path": "/webhook",
                "shared_secret_name": "MISSING_SECRET",
            },
            {},
        )
        assert len(issues) > 0
        assert any("missing_secret" in issue.code for issue in issues)

    def test_normalize_inbound_event_dict(self):
        """Test event normalization with dict payload."""
        plugin = WebhookTransportPlugin()
        result = plugin.normalize_inbound_event({
            "event_type": "message",
            "text": "Hello",
            "session_id": "test-session",
        })
        assert result["kind"] == "webhook"
        assert result["event_type"] == "message"
        assert result["text"] == "Hello"


class TestTelegramTransport:
    """Test Telegram transport plugin."""

    def test_build_plugin(self):
        """Test plugin factory function."""
        from nagient.bundled_transports.telegram.transport import build_plugin

        plugin = build_plugin()
        assert isinstance(plugin, TelegramTransportPlugin)
        assert isinstance(plugin, BaseTransportPlugin)

    def test_validate_config_missing_secret_ref(self):
        """Test config validation with missing secret reference."""
        plugin = TelegramTransportPlugin()
        issues = plugin.validate_config(
            "test_telegram",
            {},
            {},
        )
        assert len(issues) > 0
        assert any("missing_secret_ref" in issue.code for issue in issues)

    def test_validate_config_secret_not_found(self):
        """Test config validation with secret not found."""
        plugin = TelegramTransportPlugin()
        issues = plugin.validate_config(
            "test_telegram",
            {"bot_token_secret": "TELEGRAM_TOKEN"},
            {},
        )
        assert len(issues) > 0
        assert any("secret_not_found" in issue.code for issue in issues)

    def test_validate_config_valid(self):
        """Test config validation with valid settings."""
        plugin = TelegramTransportPlugin()
        issues = plugin.validate_config(
            "test_telegram",
            {"bot_token_secret": "TELEGRAM_TOKEN"},
            {"TELEGRAM_TOKEN": "123456:ABC-DEF"},
        )
        assert len(issues) == 0

    def test_validate_config_invalid_parse_mode(self):
        """Test config validation with invalid parse mode."""
        plugin = TelegramTransportPlugin()
        issues = plugin.validate_config(
            "test_telegram",
            {
                "bot_token_secret": "TELEGRAM_TOKEN",
                "default_parse_mode": "InvalidMode",
            },
            {"TELEGRAM_TOKEN": "123456:ABC-DEF"},
        )
        assert len(issues) > 0
        assert any("invalid_parse_mode" in issue.code for issue in issues)

    def test_normalize_message_event(self):
        """Test normalization of message event."""
        plugin = TelegramTransportPlugin()
        result = plugin.normalize_inbound_event({
            "message": {
                "message_id": 123,
                "text": "Hello",
                "chat": {"id": 456, "type": "private"},
                "from": {"id": 789, "first_name": "Test"},
            }
        })
        assert result["kind"] == "telegram"
        assert result["event_type"] == "message"
        assert result["text"] == "Hello"
        assert result["session_id"] == "telegram:456"

    def test_normalize_command_event(self):
        """Test normalization of command event."""
        plugin = TelegramTransportPlugin()
        result = plugin.normalize_inbound_event({
            "message": {
                "message_id": 123,
                "text": "/start",
                "chat": {"id": 456},
                "from": {"id": 789},
            }
        })
        assert result["kind"] == "telegram"
        assert result["event_type"] == "command"
        assert result["command"] == "start"

    def test_self_test_invalid_token_format(self):
        """Test self-test with invalid token format."""
        plugin = TelegramTransportPlugin()
        issues = plugin.self_test(
            "test_telegram",
            {"bot_token_secret": "TELEGRAM_TOKEN"},
            {"TELEGRAM_TOKEN": "invalid-token"},
        )
        assert len(issues) > 0
        assert any("invalid_token_format" in issue.code for issue in issues)

    def test_self_test_valid_token_format(self):
        """Test self-test with valid token format."""
        plugin = TelegramTransportPlugin()
        issues = plugin.self_test(
            "test_telegram",
            {"bot_token_secret": "TELEGRAM_TOKEN"},
            {"TELEGRAM_TOKEN": "123456:ABC-DEF"},
        )
        assert len(issues) == 0
