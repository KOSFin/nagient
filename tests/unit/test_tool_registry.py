from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nagient.tools.registry import ToolPluginRegistry
from nagient.tools.scaffold import scaffold_tool_plugin


class ToolPluginRegistryTests(unittest.TestCase):
    def test_registry_discovers_builtins_and_custom_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tools_dir = Path(temp_dir) / "tools"
            scaffold_tool_plugin(
                plugin_id="custom.tool",
                output_dir=tools_dir / "custom.tool",
            )

            discovery = ToolPluginRegistry().discover(tools_dir)

            self.assertIn("workspace.fs", discovery.plugins)
            self.assertIn("system.backup", discovery.plugins)
            self.assertIn("custom.tool", discovery.plugins)
            self.assertTrue(discovery.plugins["custom.tool"].manifest.config_fields)
            self.assertEqual(discovery.issues, [])


if __name__ == "__main__":
    unittest.main()
