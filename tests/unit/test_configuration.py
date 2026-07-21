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
            self.assertTrue(
                any(
                    tool.tool_id == "github_api"
                    and tool.plugin_id == "nagient.github_api"
                    and not tool.enabled
                    for tool in runtime_config.tools
                )
            )
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

    def test_empty_default_provider_allows_single_enabled_provider_autoselect(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            config_file = home_dir / "config.toml"
            config_file.write_text(
                "\n".join(
                    [
                        "[agent]",
                        'default_provider = ""',
                        "",
                        "[providers.openai]",
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
            settings = Settings.from_env(
                {
                    "NAGIENT_HOME": str(home_dir),
                    "NAGIENT_CONFIG": str(config_file),
                }
            )

            runtime_config = load_runtime_configuration(settings)

            self.assertEqual(runtime_config.default_provider, "openai")

    def test_configuration_merges_partial_tool_overrides_with_default_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            config_file = home_dir / "config.toml"
            config_file.write_text(
                "\n".join(
                    [
                        "[tools.workspace_git]",
                        'plugin = "workspace.git"',
                        "enabled = true",
                        'token_secret = "GIT_CLASSIC_TOKEN"',
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
            runtime_config = load_runtime_configuration(settings)

            self.assertTrue(
                any(
                    tool.tool_id == "github_api"
                    and tool.plugin_id == "nagient.github_api"
                    and not tool.enabled
                    for tool in runtime_config.tools
                )
            )
            self.assertTrue(
                any(
                    tool.tool_id == "workspace_git"
                    and tool.plugin_id == "workspace.git"
                    and tool.enabled
                    and tool.config["token_secret"] == "GIT_CLASSIC_TOKEN"
                    for tool in runtime_config.tools
                )
            )

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

    def test_environment_only_configuration_loads_direct_and_json_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})

            runtime_config = load_runtime_configuration(
                settings,
                environ={
                    "NAGIENT_CONFIG_JSON": (
                        '{"agent":{"max_turns":20},'
                        '"providers":{"openai":{"plugin":"builtin.openai",'
                        '"enabled":true,"api_key_secret":"OPENAI_API_KEY"}},'
                        '"tools":{"github_api":{"token_secret":"GITHUB_TOKEN"}}}'
                    ),
                    "NAGIENT_AGENT_DEFAULT_PROVIDER": "openai",
                    "OPENAI_API_KEY": "sk-from-environment",
                    "NAGIENT_TOOL_SECRETS_JSON": '{"GITHUB_TOKEN":"github-from-json"}',
                },
            )

            self.assertEqual(runtime_config.agent.max_turns, 20)
            self.assertEqual(runtime_config.default_provider, "openai")
            self.assertEqual(
                runtime_config.secrets["OPENAI_API_KEY"],
                "sk-from-environment",
            )
            self.assertEqual(
                runtime_config.tool_secrets["GITHUB_TOKEN"],
                "github-from-json",
            )

    def test_granular_environment_override_wins_over_json_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})

            runtime_config = load_runtime_configuration(
                settings,
                environ={
                    "NAGIENT_CONFIG_JSON": (
                        '{"providers":{"openai":{"plugin":"builtin.openai",'
                        '"enabled":false,"model":"json-model"}}}'
                    ),
                    "NAGIENT_PROVIDER__OPENAI__ENABLED": "true",
                    "NAGIENT_PROVIDER__OPENAI__MODEL": "env-model",
                },
            )

            self.assertTrue(runtime_config.providers[0].enabled)
            self.assertEqual(runtime_config.providers[0].config["model"], "env-model")

    def test_environment_transport_overrides_are_merged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})

            runtime_config = load_runtime_configuration(
                settings,
                environ={
                    "NAGIENT_TRANSPORT__TELEGRAM__PLUGIN": "nagient.telegram",
                    "NAGIENT_TRANSPORT__TELEGRAM__ENABLED": "true",
                    "NAGIENT_TRANSPORT__TELEGRAM__BOT_TOKEN_SECRET": "TELEGRAM_BOT_TOKEN",
                    "NAGIENT_TRANSPORT__TELEGRAM__DEFAULT_CHAT_ID": "1522105862",
                },
            )

            self.assertEqual(len(runtime_config.transports), 1)
            self.assertEqual(runtime_config.transports[0].transport_id, "telegram")
            self.assertEqual(runtime_config.transports[0].plugin_id, "nagient.telegram")
            self.assertTrue(runtime_config.transports[0].enabled)
            self.assertEqual(
                runtime_config.transports[0].config["default_chat_id"],
                1522105862,
            )

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

    def test_single_enabled_provider_becomes_effective_default_when_agent_default_is_absent(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            config_file = home_dir / "config.toml"
            config_file.write_text(
                "\n".join(
                    [
                        "[providers.openai]",
                        'plugin = "builtin.openai"',
                        "enabled = true",
                        'auth = "api_key"',
                        'api_key_secret = "OPENAI_API_KEY"',
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

            runtime_config = load_runtime_configuration(settings)

            self.assertEqual(runtime_config.default_provider, "openai")

    def test_agent_memory_and_logging_settings_load_from_config_and_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            config_file = home_dir / "config.toml"
            config_file.write_text(
                "\n".join(
                    [
                        "[agent]",
                        'system_prompt_file = "./prompts/custom.md"',
                        "max_turns = 6",
                        "",
                        "[agent.memory]",
                        "hard_message_limit = 120",
                        "dynamic_focus_enabled = false",
                        "dynamic_focus_messages = 12",
                        "summary_trigger_messages = 18",
                        "retrieval_max_results = 9",
                        "",
                        "[agent.logging]",
                        'level = "debug"',
                        "json_logs = true",
                        "log_events = false",
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
                    "NAGIENT_AGENT_MEMORY__DYNAMIC_FOCUS_ENABLED": "true",
                    "NAGIENT_AGENT_LOGGING__LEVEL": "warning",
                },
            )

            self.assertEqual(runtime_config.agent.max_turns, 6)
            self.assertTrue(runtime_config.agent.memory.dynamic_focus_enabled)
            self.assertEqual(runtime_config.agent.memory.hard_message_limit, 120)
            self.assertEqual(runtime_config.agent.logging.level, "warning")
            self.assertTrue(runtime_config.agent.logging.json_logs)
            self.assertFalse(runtime_config.agent.logging.log_events)
            self.assertEqual(
                runtime_config.agent.system_prompt_file,
                (home_dir / "prompts" / "custom.md").resolve(),
            )

    def test_workspace_and_prompt_paths_accept_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            config_file = home_dir / "config.toml"
            config_file.write_text(
                "\n".join(
                    [
                        "[workspace]",
                        'root = "@home/project"',
                        "",
                        "[agent]",
                        'system_prompt_file = "@prompts/custom-system.md"',
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

            runtime_config = load_runtime_configuration(settings)

            self.assertEqual(runtime_config.workspace.root, (home_dir / "project").resolve())
            self.assertEqual(
                runtime_config.agent.system_prompt_file,
                (home_dir / "prompts" / "custom-system.md").resolve(),
            )


if __name__ == "__main__":
    unittest.main()
