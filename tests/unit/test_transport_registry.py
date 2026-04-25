from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nagient.plugins.registry import TransportPluginRegistry
from nagient.plugins.scaffold import scaffold_transport_plugin


class TransportPluginRegistryTests(unittest.TestCase):
    def test_registry_discovers_builtins_and_custom_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir) / "plugins"
            scaffold_transport_plugin(
                plugin_id="custom.echo",
                output_dir=plugins_dir / "custom.echo",
            )

            discovery = TransportPluginRegistry().discover(plugins_dir)

            self.assertIn("builtin.console", discovery.plugins)
            self.assertIn("builtin.webhook", discovery.plugins)
            self.assertIn("builtin.telegram", discovery.plugins)
            self.assertIn("custom.echo", discovery.plugins)
            self.assertEqual(discovery.issues, [])


if __name__ == "__main__":
    unittest.main()
