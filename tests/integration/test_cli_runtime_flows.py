from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.bootstrap import PROJECT_ROOT, SRC_ROOT


class CliRuntimeFlowsTests(unittest.TestCase):
    def test_init_preflight_scaffold_and_transport_list_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            env = {
                **os.environ,
                "PYTHONPATH": str(SRC_ROOT),
                "NAGIENT_HOME": str(home_dir),
            }

            init_process = subprocess.run(
                [sys.executable, "-m", "nagient", "init", "--format", "json"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            init_payload = json.loads(init_process.stdout)
            self.assertTrue((home_dir / "config.toml").exists())
            self.assertTrue((home_dir / "secrets.env").exists())
            self.assertIn(str((home_dir / "config.toml").resolve()), init_payload["written_files"])

            preflight_process = subprocess.run(
                [sys.executable, "-m", "nagient", "preflight", "--format", "json"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            preflight_payload = json.loads(preflight_process.stdout)
            self.assertEqual(preflight_payload["status"], "ready")
            self.assertTrue(preflight_payload["can_activate"])

            scaffold_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nagient",
                    "transport",
                    "scaffold",
                    "--plugin-id",
                    "custom.echo",
                    "--format",
                    "json",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            scaffold_payload = json.loads(scaffold_process.stdout)
            plugin_dir = home_dir / "plugins" / "custom.echo"
            self.assertEqual(scaffold_payload["plugin_id"], "custom.echo")
            self.assertTrue((plugin_dir / "plugin.toml").exists())

            transport_list_process = subprocess.run(
                [sys.executable, "-m", "nagient", "transport", "list", "--format", "json"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            list_payload = json.loads(transport_list_process.stdout)
            plugin_ids = {item["plugin_id"] for item in list_payload["plugins"]}
            self.assertIn("builtin.console", plugin_ids)
            self.assertIn("custom.echo", plugin_ids)

    def test_reconcile_and_serve_once_write_activation_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            env = {
                **os.environ,
                "PYTHONPATH": str(SRC_ROOT),
                "NAGIENT_HOME": str(home_dir),
            }
            subprocess.run(
                [sys.executable, "-m", "nagient", "init", "--format", "json"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            reconcile_process = subprocess.run(
                [sys.executable, "-m", "nagient", "reconcile", "--format", "json"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            reconcile_payload = json.loads(reconcile_process.stdout)
            self.assertEqual(reconcile_payload["status"], "ready")
            self.assertTrue((home_dir / "state" / "activation-report.json").exists())

            subprocess.run(
                [sys.executable, "-m", "nagient", "serve", "--once"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            heartbeat = json.loads(
                (home_dir / "state" / "heartbeat.json").read_text(encoding="utf-8")
            )
            self.assertEqual(heartbeat["runtime_status"], "ready")
            self.assertEqual(heartbeat["transports"][0]["plugin_id"], "builtin.console")


if __name__ == "__main__":
    unittest.main()
