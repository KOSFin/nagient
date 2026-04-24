from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nagient.app.settings import Settings


class SettingsTests(unittest.TestCase):
    def test_settings_read_defaults_from_toml(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            config_file = home_dir / "config.toml"
            config_file.write_text(
                "\n".join(
                    [
                        "[updates]",
                        'channel = "beta"',
                        'base_url = "https://updates.test/nagient"',
                        "",
                        "[runtime]",
                        "heartbeat_interval_seconds = 12",
                        "",
                        "[docker]",
                        'project_name = "nagient-dev"',
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

            self.assertEqual(settings.channel, "beta")
            self.assertEqual(settings.update_base_url, "https://updates.test/nagient")
            self.assertEqual(settings.heartbeat_interval_seconds, 12)
            self.assertEqual(settings.docker_project_name, "nagient-dev")

    def test_environment_overrides_file_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            config_file = home_dir / "config.toml"
            config_file.write_text("[updates]\nchannel = \"stable\"\n", encoding="utf-8")

            settings = Settings.from_env(
                {
                    "NAGIENT_HOME": str(home_dir),
                    "NAGIENT_CONFIG": str(config_file),
                    "NAGIENT_CHANNEL": "edge",
                }
            )

            self.assertEqual(settings.channel, "edge")


if __name__ == "__main__":
    unittest.main()
