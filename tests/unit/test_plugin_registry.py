"""
Unit tests for plugin registry and discovery.
"""

from __future__ import annotations

from pathlib import Path

from nagient.plugins.registry import TransportPluginRegistry


class TestTransportPluginRegistry:
    """Test transport plugin registry."""

    def test_discover_bundled_transports(self):
        """Test that bundled transports are discovered."""
        registry = TransportPluginRegistry()
        # Pass non-existent path to only discover bundled plugins
        discovery = registry.discover(Path("/nonexistent"))

        # Should find bundled transports
        assert len(discovery.plugins) >= 3

        # Check for known bundled transports
        plugin_ids = set(discovery.plugins.keys())
        assert "builtin.telegram" in plugin_ids
        assert "builtin.console" in plugin_ids
        assert "builtin.webhook" in plugin_ids

    def test_telegram_plugin_manifest(self):
        """Test Telegram plugin manifest."""
        registry = TransportPluginRegistry()
        discovery = registry.discover(Path("/nonexistent"))

        telegram = discovery.plugins.get("builtin.telegram")
        assert telegram is not None
        assert telegram.manifest.display_name == "Telegram Transport"
        assert telegram.manifest.namespace == "telegram"
        assert telegram.manifest.plugin_id == "builtin.telegram"

        # Check required slots
        assert "send_message" in telegram.manifest.required_slots
        assert "poll_inbound_events" in telegram.manifest.required_slots

    def test_console_plugin_manifest(self):
        """Test Console plugin manifest."""
        registry = TransportPluginRegistry()
        discovery = registry.discover(Path("/nonexistent"))

        console = discovery.plugins.get("builtin.console")
        assert console is not None
        assert console.manifest.display_name == "Console Transport"
        assert console.manifest.namespace == "console"

    def test_webhook_plugin_manifest(self):
        """Test Webhook plugin manifest."""
        registry = TransportPluginRegistry()
        discovery = registry.discover(Path("/nonexistent"))

        webhook = discovery.plugins.get("builtin.webhook")
        assert webhook is not None
        assert webhook.manifest.display_name == "Webhook Transport"
        assert webhook.manifest.namespace == "webhook"

    def test_plugin_implementation_instantiation(self):
        """Test that plugin implementations can be instantiated."""
        registry = TransportPluginRegistry()
        discovery = registry.discover(Path("/nonexistent"))

        for _plugin_id, plugin in discovery.plugins.items():
            # Implementation should be already loaded
            assert plugin.implementation is not None
            # Should have required methods
            assert hasattr(plugin.implementation, "send_message")
            assert hasattr(plugin.implementation, "normalize_inbound_event")

    def test_discovery_with_user_plugins_dir(self, tmp_path):
        """Test discovery with user plugins directory."""
        registry = TransportPluginRegistry()
        discovery = registry.discover(tmp_path)

        # Should still find bundled plugins
        assert len(discovery.plugins) >= 3
        assert "builtin.telegram" in discovery.plugins

    def test_no_duplicate_plugin_ids(self):
        """Test that there are no duplicate plugin IDs."""
        registry = TransportPluginRegistry()
        discovery = registry.discover(Path("/nonexistent"))

        plugin_ids = list(discovery.plugins.keys())
        assert len(plugin_ids) == len(set(plugin_ids))
