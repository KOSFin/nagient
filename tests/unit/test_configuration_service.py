from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nagient.app.container import build_container
from nagient.app.settings import Settings


class ConfigurationServiceTests(unittest.TestCase):
    def test_external_transport_configuration_points_to_plugin_installer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)

            with self.assertRaisesRegex(
                ValueError,
                "nagient plugin install nagient.telegram",
            ):
                container.configuration_service.configure_transport("telegram")

    def test_secret_reference_updates_reject_raw_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)

            with self.assertRaisesRegex(ValueError, "secret name like MY_SECRET"):
                container.configuration_service.configure_transport(
                    "webhook",
                    config_updates={"shared_secret_name": "123456:webhook-secret"},
                )

    def test_tool_secret_reference_updates_reject_raw_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)

            with self.assertRaisesRegex(ValueError, "secret name like MY_SECRET"):
                container.configuration_service.configure_tool(
                    "workspace_git",
                    config_updates={"token_secret": "ghp-raw-token"},
                )

    def test_first_enabled_provider_becomes_default_automatically(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)

            payload = container.configuration_service.configure_provider(
                "openai",
                enabled=True,
                config_updates={
                    "auth": "api_key",
                    "api_key_secret": "OPENAI_API_KEY",
                },
            )

            self.assertTrue(payload["default"])
            config_text = settings.config_file.read_text(encoding="utf-8")
            self.assertIn('default_provider = "openai"', config_text)

    def test_new_provider_is_enabled_and_selected_without_enable_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)

            payload = container.configuration_service.configure_provider(
                "openai",
                config_updates={
                    "auth": "api_key",
                    "api_key_secret": "OPENAI_API_KEY",
                },
            )

            self.assertTrue(payload["enabled"])
            self.assertTrue(payload["auto_enabled"])
            self.assertTrue(payload["auto_defaulted"])
            config_text = settings.config_file.read_text(encoding="utf-8")
            self.assertIn("enabled = true", config_text)
            self.assertIn('default_provider = "openai"', config_text)

    def test_configure_paths_accepts_runtime_dirs_and_writes_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)

            payload = container.configuration_service.configure_paths(
                {
                    "state_dir": str(home_dir / "state"),
                    "log_dir": str(home_dir / "logs"),
                    "releases_dir": str(home_dir / "releases" / "stable"),
                }
            )

            self.assertEqual(payload["paths"]["state_dir"], "@state")
            self.assertEqual(payload["paths"]["log_dir"], "@logs")
            self.assertEqual(payload["paths"]["releases_dir"], "@releases/stable")

    def test_configure_workspace_writes_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)

            payload = container.configuration_service.configure_workspace(
                root=str(home_dir / "workspace"),
            )

            self.assertEqual(payload["workspace"]["root"], "@home/workspace")


if __name__ == "__main__":
    unittest.main()
