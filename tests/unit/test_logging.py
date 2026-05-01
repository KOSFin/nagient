from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from nagient.app.settings import Settings
from nagient.infrastructure.logging import RuntimeLogger


class RuntimeLoggerTests(unittest.TestCase):
    def test_logger_writes_component_log_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})

            RuntimeLogger(settings, "runtime-test").info(
                "runtime.event",
                "Hello world.",
                session_id="demo",
            )

            component_path = settings.log_dir / "runtime-test.log"
            self.assertTrue(component_path.exists())
            self.assertIn("Hello world.", component_path.read_text(encoding="utf-8"))
            self.assertFalse((settings.log_dir / "events.log").exists())

    def test_logger_honors_level_and_json_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            config_file = home_dir / "config.toml"
            config_file.write_text(
                "\n".join(
                    [
                        "[agent.logging]",
                        'level = "warning"',
                        "json_logs = true",
                        "log_events = true",
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
            logger = RuntimeLogger(settings, "runtime-test")

            logger.info("runtime.info", "This should be filtered.")
            logger.warning("runtime.warning", "This should be written.")

            component_path = settings.log_dir / "runtime-test.log"
            events_path = settings.log_dir / "events.log"
            self.assertIn("This should be written.", component_path.read_text(encoding="utf-8"))
            self.assertNotIn(
                "This should be filtered.",
                component_path.read_text(encoding="utf-8"),
            )
            payload = [
                json.loads(line)
                for line in events_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(payload), 1)
            self.assertEqual(payload[0]["event"], "runtime.warning")


if __name__ == "__main__":
    unittest.main()
