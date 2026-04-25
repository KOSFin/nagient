from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.bootstrap import PROJECT_ROOT, SRC_ROOT


class CliToolRuntimeFlowsTests(unittest.TestCase):
    def test_tool_backup_and_workflow_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
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

            config_file = home_dir / "config.toml"
            config_file.write_text(
                config_file.read_text(encoding="utf-8").replace(
                    'root = ""',
                    f'root = "{workspace_root}"',
                ),
                encoding="utf-8",
            )

            write_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nagient",
                    "tool",
                    "invoke",
                    "workspace.fs.write_text",
                    "--tool-id",
                    "workspace_fs",
                    "--args-json",
                    json.dumps({"path": "note.txt", "content": "hello"}),
                    "--format",
                    "json",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            write_payload = json.loads(write_process.stdout)
            self.assertEqual(write_payload["status"], "success")

            backup_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nagient",
                    "tool",
                    "invoke",
                    "system.backup.create",
                    "--tool-id",
                    "system_backup",
                    "--args-json",
                    json.dumps({"reason": "manual"}),
                    "--format",
                    "json",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            backup_payload = json.loads(backup_process.stdout)
            snapshot_id = backup_payload["output"]["snapshot_id"]

            restore_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nagient",
                    "tool",
                    "invoke",
                    "system.backup.restore",
                    "--tool-id",
                    "system_backup",
                    "--args-json",
                    json.dumps({"snapshot_id": snapshot_id}),
                    "--format",
                    "json",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            restore_payload = json.loads(restore_process.stdout)
            self.assertEqual(restore_payload["status"], "approval_required")

            approval_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nagient",
                    "approval",
                    "respond",
                    restore_payload["approval_request_id"],
                    "--decision",
                    "approve",
                    "--format",
                    "json",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            approval_payload = json.loads(approval_process.stdout)
            self.assertEqual(approval_payload["status"], "approved")


if __name__ == "__main__":
    unittest.main()
