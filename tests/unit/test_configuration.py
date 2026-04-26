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
            self.assertEqual(
                runtime_config.secrets,
                {"NAGIENT_WEBHOOK_SHARED_SECRET": "super-secret"},
            )
            self.assertEqual(len(runtime_config.transports), 1)
            self.assertEqual(runtime_config.transports[0].transport_id, "webhook_main")
            self.assertEqual(runtime_config.transports[0].plugin_id, "builtin.webhook")
            self.assertEqual(runtime_config.transports[0].config["path"], "/ingest")

    def test_configuration_loads_provider_profiles_and_agent_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            config_file = home_dir / "config.toml"
            config_file.write_text(
                "\n".join(
                    [
                        "[agent]",
                        'default_provider = "openai_main"',
                        "require_provider = true",
                        "",
                        "[providers.openai_main]",
                        'plugin = "builtin.openai"',
                        "enabled = true",
                        'auth = "api_key"',
                        'api_key_secret = "OPENAI_API_KEY"',
                        'model = "gpt-4.1-mini"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            secrets_file = home_dir / "secrets.env"
            secrets_file.write_text("OPENAI_API_KEY=sk-test\n", encoding="utf-8")

            settings = Settings.from_env(
                {
                    "NAGIENT_HOME": str(home_dir),
                    "NAGIENT_CONFIG": str(config_file),
                    "NAGIENT_SECRETS_FILE": str(secrets_file),
                }
            )
            runtime_config = load_runtime_configuration(settings)

            self.assertEqual(runtime_config.default_provider, "openai_main")
            self.assertTrue(runtime_config.require_provider)
            self.assertEqual(len(runtime_config.providers), 1)
            self.assertEqual(runtime_config.providers[0].provider_id, "openai_main")
            self.assertEqual(runtime_config.providers[0].plugin_id, "builtin.openai")
            self.assertEqual(runtime_config.providers[0].config["model"], "gpt-4.1-mini")

    def test_environment_provider_overrides_are_merged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})

            runtime_config = load_runtime_configuration(
                settings,
                environ={
                    "NAGIENT_AGENT_DEFAULT_PROVIDER": "openai",
                    "NAGIENT_AGENT_REQUIRE_PROVIDER": "true",
                    "NAGIENT_PROVIDER__OPENAI__PLUGIN": "builtin.openai",
                    "NAGIENT_PROVIDER__OPENAI__ENABLED": "true",
                    "NAGIENT_PROVIDER__OPENAI__AUTH": "api_key",
                    "NAGIENT_PROVIDER__OPENAI__API_KEY_SECRET": "OPENAI_API_KEY",
                    "NAGIENT_PROVIDER__OPENAI__MODEL": "gpt-4.1-mini",
                },
            )

            self.assertEqual(runtime_config.default_provider, "openai")
            self.assertTrue(runtime_config.require_provider)
            self.assertEqual(len(runtime_config.providers), 1)
            self.assertEqual(runtime_config.providers[0].provider_id, "openai")
            self.assertTrue(runtime_config.providers[0].enabled)

    def test_environment_provider_overrides_accept_underscore_alias_for_hyphenated_ids(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            config_file = home_dir / "config.toml"
            config_file.write_text(
                "\n".join(
                    [
                        "[providers.openai-codex]",
                        'plugin = "builtin.openai_codex"',
                        "enabled = false",
                        'auth = "oauth_browser"',
                        'redirect_uri = "http://127.0.0.1:1455/auth/callback"',
                        'api_key_secret = "CODEX_API_KEY"',
                        'model = "gpt-5-codex"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            settings = Settings.from_env(
                {
                    "NAGIENT_HOME": str(home_dir),
                    "NAGIENT_CONFIG": str(config_file),
                }
            )

            runtime_config = load_runtime_configuration(
                settings,
                environ={
                    "NAGIENT_PROVIDER__OPENAI_CODEX__ENABLED": "true",
                    "NAGIENT_PROVIDER__OPENAI_CODEX__MODEL": "gpt-5-codex",
                },
            )

            self.assertEqual(len(runtime_config.providers), 1)
            self.assertEqual(runtime_config.providers[0].provider_id, "openai-codex")
            self.assertTrue(runtime_config.providers[0].enabled)


if __name__ == "__main__":
    unittest.main()
