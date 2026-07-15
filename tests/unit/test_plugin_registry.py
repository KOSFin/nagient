from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nagient.plugins.registry import TransportPluginRegistry

_MISSING_DIR = Path("/nonexistent-nagient-plugins-dir")


class TransportPluginRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = TransportPluginRegistry()

    def test_discover_bundled_transports(self) -> None:
        discovery = self.registry.discover(_MISSING_DIR)
        plugin_ids = set(discovery.plugins)
        self.assertIn("builtin.telegram", plugin_ids)
        self.assertIn("builtin.console", plugin_ids)
        self.assertIn("builtin.webhook", plugin_ids)

    def test_bundled_discovery_reports_no_errors(self) -> None:
        discovery = self.registry.discover(_MISSING_DIR)
        errors = [issue for issue in discovery.issues if issue.severity == "error"]
        self.assertEqual(errors, [])

    def test_telegram_plugin_manifest(self) -> None:
        discovery = self.registry.discover(_MISSING_DIR)
        telegram = discovery.plugins.get("builtin.telegram")
        self.assertIsNotNone(telegram)
        assert telegram is not None
        self.assertEqual(telegram.manifest.display_name, "Telegram Transport")
        self.assertEqual(telegram.manifest.namespace, "telegram")
        self.assertIn("send_message", telegram.manifest.required_slots)
        self.assertIn("poll_inbound_events", telegram.manifest.required_slots)

    def test_console_plugin_manifest(self) -> None:
        discovery = self.registry.discover(_MISSING_DIR)
        console = discovery.plugins.get("builtin.console")
        self.assertIsNotNone(console)
        assert console is not None
        self.assertEqual(console.manifest.display_name, "Console Transport")
        self.assertEqual(console.manifest.namespace, "console")

    def test_webhook_plugin_manifest(self) -> None:
        discovery = self.registry.discover(_MISSING_DIR)
        webhook = discovery.plugins.get("builtin.webhook")
        self.assertIsNotNone(webhook)
        assert webhook is not None
        self.assertEqual(webhook.manifest.display_name, "Webhook Transport")
        self.assertEqual(webhook.manifest.namespace, "webhook")

    def test_plugin_implementations_are_loaded(self) -> None:
        discovery = self.registry.discover(_MISSING_DIR)
        for plugin in discovery.plugins.values():
            self.assertIsNotNone(plugin.implementation)
            self.assertTrue(hasattr(plugin.implementation, "send_message"))
            self.assertTrue(hasattr(plugin.implementation, "normalize_inbound_event"))

    def test_discovery_with_empty_user_dir_keeps_bundled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            discovery = self.registry.discover(Path(tmp))
        self.assertIn("builtin.telegram", discovery.plugins)

    def test_no_duplicate_plugin_ids(self) -> None:
        discovery = self.registry.discover(_MISSING_DIR)
        plugin_ids = list(discovery.plugins)
        self.assertEqual(len(plugin_ids), len(set(plugin_ids)))


if __name__ == "__main__":
    unittest.main()
