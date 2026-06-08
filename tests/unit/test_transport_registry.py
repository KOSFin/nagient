from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nagient.plugins.base import TransportRuntimeContext
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
            telegram = discovery.plugins["builtin.telegram"]
            self.assertIn("bundled_transports", telegram.source)
            self.assertEqual(telegram.manifest.config_schema_file, "schema.json")
            self.assertEqual(telegram.manifest.log_channels[0].name, "transport.telegram")
            self.assertIn("telegram.sendTyping", telegram.manifest.custom_functions)
            self.assertTrue(discovery.plugins["custom.echo"].manifest.config_fields)
            self.assertEqual(discovery.issues, [])

    def test_registry_discovers_process_runtime_transport(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir) / "plugins"
            plugin_dir = plugins_dir / "custom.process"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "instructions.md").write_text("Process transport.\n", encoding="utf-8")
            (plugin_dir / "plugin.toml").write_text(
                "\n".join(
                    [
                        'id = "custom.process"',
                        'type = "transport"',
                        'version = "0.1.0"',
                        'display_name = "Custom Process"',
                        'namespace = "process"',
                        'runtime = "process"',
                        'entrypoint = "transport.py"',
                        'instructions_file = "instructions.md"',
                        "",
                        "required_config = []",
                        "optional_config = []",
                        "secret_config = []",
                        'custom_functions = ["process.react"]',
                        "",
                        "[required_slots]",
                        'send_message = "process.sendMessage"',
                        'send_notification = "process.sendNotification"',
                        'normalize_inbound_event = "process.normalizeInboundEvent"',
                        'poll_inbound_events = "process.pollInboundEvents"',
                        'healthcheck = "process.healthcheck"',
                        'selftest = "process.selftest"',
                        'start = "process.start"',
                        'stop = "process.stop"',
                        "",
                        "[function_bindings]",
                        '"process.sendMessage" = "send_message"',
                        '"process.sendNotification" = "send_notification"',
                        '"process.normalizeInboundEvent" = "normalize_inbound_event"',
                        '"process.pollInboundEvents" = "poll_inbound_events"',
                        '"process.healthcheck" = "healthcheck"',
                        '"process.selftest" = "self_test"',
                        '"process.start" = "start"',
                        '"process.stop" = "stop"',
                        '"process.react" = "react"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            (plugin_dir / "transport.py").write_text(
                "\n".join(
                    [
                        "import json, sys",
                        "payload = json.loads(sys.stdin.read())",
                        "method = payload.get('method')",
                        "if method in {'validate_config', 'selftest', 'healthcheck'}:",
                        "    print(json.dumps({'status': 'success', 'issues': []}))",
                        "elif method == 'poll_inbound_events':",
                        "    print(json.dumps({'status': 'success', 'output': []}))",
                        "elif method == 'normalize_inbound_event':",
                        (
                            "    print(json.dumps({'status': 'success', 'output': "
                            "{'event_type': 'message', 'payload': "
                            "payload.get('payload')}}))"
                        ),
                        "else:",
                        (
                            "    print(json.dumps({'status': 'success', 'output': "
                            "{'method': method, 'payload': payload.get('payload', {})}}))"
                        ),
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            discovery = TransportPluginRegistry().discover(plugins_dir)
            plugin = discovery.plugins["custom.process"]
            plugin.implementation.bind_runtime(
                "process",
                TransportRuntimeContext(state_dir=Path(temp_dir), log=lambda message: None),
            )

            self.assertEqual(plugin.runtime, "process")
            self.assertEqual(
                plugin.implementation.send_message({"text": "hello"}),
                {"method": "send_message", "payload": {"text": "hello"}},
            )


if __name__ == "__main__":
    unittest.main()
