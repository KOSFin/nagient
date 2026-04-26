from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nagient.providers.registry import ProviderPluginRegistry
from nagient.providers.scaffold import scaffold_provider_plugin


class ProviderPluginRegistryTests(unittest.TestCase):
    def test_registry_discovers_builtins_and_custom_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            providers_dir = Path(temp_dir) / "providers"
            scaffold_provider_plugin(
                plugin_id="custom.provider",
                output_dir=providers_dir / "custom.provider",
            )

            discovery = ProviderPluginRegistry().discover(providers_dir)

            self.assertIn("builtin.openai", discovery.plugins)
            self.assertIn("builtin.openai_codex", discovery.plugins)
            self.assertIn("builtin.deepseek", discovery.plugins)
            self.assertIn("custom.provider", discovery.plugins)
            self.assertEqual(discovery.issues, [])


if __name__ == "__main__":
    unittest.main()
