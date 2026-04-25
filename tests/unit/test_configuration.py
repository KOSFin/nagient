from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nagient.app.configuration import load_runtime_configuration
from nagient.app.settings import Settings


class ConfigurationTests(unittest.TestCase):
    def test_missing_config_defaults_to_console_transport(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})

            runtime_config = load_runtime_configuration(settings)

            self.assertTrue(runtime_config.safe_mode)
            self.assertEqual(len(runtime_config.transports), 1)
            self.assertEqual(runtime_config.transports[0].plugin_id, "builtin.console")
            self.assertEqual(runtime_config.secrets, {})

    def test_configuration_loads_transport_definitions_and_secret_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            config_file = home_dir / "config.toml"
            config_file.write_text(
                "\n".join(
                    [
                        "[runtime]",
                        "safe_mode = false",
                        "",
                        "[transports.webhook_main]",
                        'plugin = "builtin.webhook"',
                        "enabled = true",
                        'path = "/ingest"',
                        "listen_port = 9090",
                        'shared_secret_name = "NAGIENT_WEBHOOK_SHARED_SECRET"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            secrets_file = home_dir / "secrets.env"
            secrets_file.write_text(
                "NAGIENT_WEBHOOK_SHARED_SECRET=super-secret\n",
                encoding="utf-8",
            )

            settings = Settings.from_env(
                {
                    "NAGIENT_HOME": str(home_dir),
                    "NAGIENT_CONFIG": str(config_file),
                    "NAGIENT_SECRETS_FILE": str(secrets_file),
                }
            )
            runtime_config = load_runtime_configuration(settings)

            self.assertFalse(runtime_config.safe_mode)
            self.assertEqual(runtime_config.secrets, {"NAGIENT_WEBHOOK_SHARED_SECRET": "super-secret"})
            self.assertEqual(len(runtime_config.transports), 1)
            self.assertEqual(runtime_config.transports[0].transport_id, "webhook_main")
            self.assertEqual(runtime_config.transports[0].plugin_id, "builtin.webhook")
            self.assertEqual(runtime_config.transports[0].config["path"], "/ingest")


if __name__ == "__main__":
    unittest.main()
