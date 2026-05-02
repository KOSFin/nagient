from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nagient.app.settings import Settings
from nagient.application.services.preflight_service import PreflightService
from nagient.plugins.manager import TransportManager
from nagient.plugins.registry import TransportPluginRegistry
from nagient.providers.manager import ProviderManager
from nagient.providers.registry import ProviderPluginRegistry
from nagient.providers.storage import FileCredentialStore


class PreflightServiceTests(unittest.TestCase):
    def test_safe_mode_blocks_activation_when_enabled_transport_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            config_file = home_dir / "config.toml"
            config_file.write_text(
                "\n".join(
                    [
                        "[runtime]",
                        "safe_mode = true",
                        "",
                        "[transports.console]",
                        'plugin = "builtin.console"',
                        "enabled = true",
                        "",
                        "[transports.telegram]",
                        'plugin = "builtin.telegram"',
                        "enabled = true",
                        'bot_token_secret = "TELEGRAM_BOT_TOKEN"',
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
            service = PreflightService(
                settings=settings,
                plugin_registry=TransportPluginRegistry(),
                transport_manager=TransportManager(),
                provider_registry=ProviderPluginRegistry(),
                provider_manager=ProviderManager(),
                credential_store=FileCredentialStore(settings.credentials_dir),
            )

            report = service.inspect()

            self.assertEqual(report.status, "blocked")
            self.assertFalse(report.can_activate)

    def test_disabled_safe_mode_allows_degraded_activation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            config_file = home_dir / "config.toml"
            config_file.write_text(
                "\n".join(
                    [
                        "[runtime]",
                        "safe_mode = false",
                        "",
                        "[transports.telegram]",
                        'plugin = "builtin.telegram"',
                        "enabled = true",
                        'bot_token_secret = "TELEGRAM_BOT_TOKEN"',
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
            service = PreflightService(
                settings=settings,
                plugin_registry=TransportPluginRegistry(),
                transport_manager=TransportManager(),
                provider_registry=ProviderPluginRegistry(),
                provider_manager=ProviderManager(),
                credential_store=FileCredentialStore(settings.credentials_dir),
            )

            report = service.inspect()

            self.assertEqual(report.status, "degraded")
            self.assertTrue(report.can_activate)

    def test_safe_mode_keeps_activation_available_when_tool_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            config_file = home_dir / "config.toml"
            config_file.write_text(
                "\n".join(
                    [
                        "[runtime]",
                        "safe_mode = true",
                        "",
                        "[transports.console]",
                        'plugin = "builtin.console"',
                        "enabled = true",
                        "",
                        "[tools.workspace_git]",
                        'plugin = "workspace.git"',
                        "enabled = true",
                        'username = "ddwnbot"',
                        'token_secret = "MISSING_GIT_TOKEN"',
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
            service = PreflightService(
                settings=settings,
                plugin_registry=TransportPluginRegistry(),
                transport_manager=TransportManager(),
                provider_registry=ProviderPluginRegistry(),
                provider_manager=ProviderManager(),
                credential_store=FileCredentialStore(settings.credentials_dir),
            )

            report = service.inspect()

            self.assertEqual(report.status, "degraded")
            self.assertTrue(report.can_activate)
            self.assertTrue(
                any(issue.code == "tool.workspace_git.missing_secret" for issue in report.issues)
            )

    def test_require_provider_blocks_activation_when_default_provider_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            config_file = home_dir / "config.toml"
            config_file.write_text(
                "\n".join(
                    [
                        "[agent]",
                        'default_provider = "openai"',
                        "require_provider = true",
                        "",
                        "[transports.console]",
                        'plugin = "builtin.console"',
                        "enabled = true",
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
            service = PreflightService(
                settings=settings,
                plugin_registry=TransportPluginRegistry(),
                transport_manager=TransportManager(),
                provider_registry=ProviderPluginRegistry(),
                provider_manager=ProviderManager(),
                credential_store=FileCredentialStore(settings.credentials_dir),
            )

            report = service.inspect()

            self.assertEqual(report.status, "blocked")
            self.assertFalse(report.can_activate)
            self.assertTrue(
                any(issue.code == "runtime.no_enabled_providers" for issue in report.issues)
            )


if __name__ == "__main__":
    unittest.main()
