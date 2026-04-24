from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

from tests.bootstrap import FIXTURES_ROOT, PROJECT_ROOT, SRC_ROOT


class CliUpdateCheckTests(unittest.TestCase):
    def test_update_check_reads_channel_manifest_from_fixture_directory(self) -> None:
        env = os.environ.copy()
        env.update(
            {
                "PYTHONPATH": str(SRC_ROOT),
                "NAGIENT_UPDATE_BASE_URL": str(FIXTURES_ROOT / "update_center"),
            }
        )
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "nagient",
                "update",
                "check",
                "--channel",
                "stable",
                "--current-version",
                "0.1.0",
                "--format",
                "json",
            ],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )

        payload = json.loads(process.stdout)
        self.assertTrue(payload["update_available"])
        self.assertEqual(payload["target_version"], "0.2.0")
        self.assertEqual(len(payload["planned_migrations"]), 1)

    def test_migrations_plan_command_returns_json(self) -> None:
        manifest_ref = str(FIXTURES_ROOT / "update_center" / "manifests" / "0.2.0.json")
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "nagient",
                "migrations",
                "plan",
                "--manifest-ref",
                manifest_ref,
                "--current-version",
                "0.1.0",
                "--format",
                "json",
            ],
            cwd=PROJECT_ROOT,
            env={**os.environ, "PYTHONPATH": str(SRC_ROOT)},
            capture_output=True,
            text=True,
            check=True,
        )

        payload = json.loads(process.stdout)
        self.assertEqual(payload["target_version"], "0.2.0")
        self.assertEqual(payload["planned_migrations"][0]["id"], "state-sync-0.2.0")


if __name__ == "__main__":
    unittest.main()
