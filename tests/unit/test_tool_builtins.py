from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nagient.app.container import build_container
from nagient.app.settings import Settings
from nagient.domain.entities.tooling import ToolExecutionRequest
from nagient.tools.builtin import _plan_shell_command


class ToolBuiltinsTests(unittest.TestCase):
    def test_workspace_shell_plan_adds_ping_count(self) -> None:
        plan = _plan_shell_command(
            "ping google.com",
            timeout_seconds=15,
            default_ping_count=4,
            normalize_infinite_commands=True,
            enforce_finite_commands=True,
        )

        self.assertEqual(plan.effective_command, "ping -c 4 google.com")
        self.assertIsNone(plan.blocked_reason)
        self.assertTrue(any("-c 4" in note for note in plan.notes))

    def test_workspace_shell_run_truncates_large_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            container = _container_with_workspace(Path(temp_dir))

            result = container.tool_service.invoke(
                ToolExecutionRequest(
                    tool_id="workspace_shell",
                    function_name="workspace.shell.run",
                    arguments={
                        "command": "printf '1234567890'",
                        "max_output_chars": 5,
                        "read_only": True,
                    },
                )
            )

            self.assertEqual(result.status, "success")
            self.assertEqual(result.output["stdout"], "12345")
            self.assertTrue(result.output["stdout_truncated"])
            self.assertFalse(result.output["blocked"])

    def test_workspace_shell_run_blocks_follow_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            container = _container_with_workspace(Path(temp_dir))

            result = container.tool_service.invoke(
                ToolExecutionRequest(
                    tool_id="workspace_shell",
                    function_name="workspace.shell.run",
                    arguments={
                        "command": "tail -f runtime.log",
                        "read_only": True,
                    },
                )
            )

            self.assertEqual(result.status, "success")
            self.assertTrue(result.output["blocked"])
            self.assertIn("continuously follow output", result.output["blocked_reason"])

    def test_workspace_shell_run_marks_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            container = _container_with_workspace(Path(temp_dir))

            result = container.tool_service.invoke(
                ToolExecutionRequest(
                    tool_id="workspace_shell",
                    function_name="workspace.shell.run",
                    arguments={
                        "command": "sleep 5",
                        "timeout_seconds": 1,
                        "read_only": True,
                    },
                )
            )

            self.assertEqual(result.status, "success")
            self.assertTrue(result.output["timed_out"])
            self.assertIsNone(result.output["exit_code"])
            self.assertTrue(
                any("runtime timeout" in note.lower() for note in result.output["notes"])
            )


def _container_with_workspace(root: Path) -> object:
    home_dir = root / "home"
    workspace_root = root / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
    container = build_container(settings)
    container.configuration_service.initialize(force=True)
    _set_workspace_root(settings.config_file, workspace_root)
    return container


def _set_workspace_root(config_file: Path, workspace_root: Path) -> None:
    config = config_file.read_text(encoding="utf-8").replace(
        'root = ""',
        f'root = "{workspace_root}"',
    )
    config_file.write_text(config, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
