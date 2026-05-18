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
            self.assertTrue(discovery.plugins["custom.provider"].manifest.config_fields)
            self.assertEqual(discovery.issues, [])

    def test_registry_discovers_process_runtime_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            providers_dir = Path(temp_dir) / "providers"
            plugin_dir = providers_dir / "custom.process"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "provider.toml").write_text(
                "\n".join(
                    [
                        'id = "custom.process"',
                        'type = "provider"',
                        'version = "0.1.0"',
                        'display_name = "Custom Process"',
                        'family = "custom"',
                        'runtime = "process"',
                        'entrypoint = "provider.py"',
                        'supported_auth_modes = ["none"]',
                        'default_auth_mode = "none"',
                        'capabilities = ["list_models"]',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            (plugin_dir / "provider.py").write_text(
                "\n".join(
                    [
                        "import json, sys",
                        "payload = json.loads(sys.stdin.read())",
                        "method = payload.get('method')",
                        "if method in {'validate_config', 'selftest', 'healthcheck'}:",
                        "    print(json.dumps({'status': 'success', 'issues': []}))",
                        "elif method == 'auth_status':",
                        (
                            "    print(json.dumps({'status': 'success', 'output': "
                            "{'authenticated': True, 'auth_mode': 'none', "
                            "'status': 'ready', 'message': 'ok'}}))"
                        ),
                        "elif method == 'list_models':",
                        (
                            "    print(json.dumps({'status': 'success', 'output': "
                            "[{'model_id': 'demo', 'display_name': 'Demo'}]}))"
                        ),
                        "else:",
                        "    print(json.dumps({'status': 'success', 'output': {}}))",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            discovery = ProviderPluginRegistry().discover(providers_dir)
            plugin = discovery.plugins["custom.process"]

            self.assertEqual(plugin.runtime, "process")
            self.assertEqual(
                plugin.implementation.auth_status(
                    "custom",
                    {},
                    {},
                    None,
                ).status,
                "ready",
            )
            self.assertEqual(
                plugin.implementation.list_models(
                    "custom",
                    {},
                    {},
                    None,
                )[0].model_id,
                "demo",
            )


if __name__ == "__main__":
    unittest.main()
