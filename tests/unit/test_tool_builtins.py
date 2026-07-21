from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from nagient.app.container import build_container
from nagient.app.settings import Settings
from nagient.domain.entities.tooling import ToolExecutionRequest
from nagient.tools.builtin import (
    _plan_shell_command,
    _workspace_git_env,
)


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

    def test_workspace_git_run_executes_read_only_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace_root = root / "workspace"
            container = _container_with_workspace(root)
            subprocess.run(
                ["git", "init"],
                cwd=workspace_root,
                capture_output=True,
                text=True,
                check=True,
            )

            result = container.tool_service.invoke(
                ToolExecutionRequest(
                    tool_id="workspace_git",
                    function_name="workspace.git.run",
                    arguments={"args": ["status", "--short"]},
                )
            )

            self.assertEqual(result.status, "success")
            self.assertEqual(result.output["exit_code"], 0)
            self.assertIsInstance(result.output["stdout"], str)

    def test_workspace_git_env_is_process_scoped_and_uses_configured_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir()
            secret_broker = SimpleNamespace(
                resolve_secret=lambda name, scope_hint=None: "ghp_demo"
            )

            env, cleanup_paths = _workspace_git_env(
                workspace_root=workspace_root,
                config={
                    "author_name": "Nagient Agent",
                    "author_email": "agent@example.com",
                    "username": "ddwnbot",
                    "token_secret": "GIT_ACCESS_TOKEN",
                },
                secret_broker=secret_broker,
            )

            try:
                self.assertEqual(env["HOME"], str(workspace_root))
                self.assertEqual(env["GIT_AUTHOR_NAME"], "Nagient Agent")
                self.assertEqual(env["GIT_AUTHOR_EMAIL"], "agent@example.com")
                self.assertEqual(env["GIT_COMMITTER_NAME"], "Nagient Agent")
                self.assertEqual(env["GIT_COMMITTER_EMAIL"], "agent@example.com")
                self.assertEqual(env["GIT_CONFIG_COUNT"], "1")
                self.assertEqual(env["GIT_CONFIG_KEY_0"], "credential.username")
                self.assertEqual(env["GIT_CONFIG_VALUE_0"], "ddwnbot")
                self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
                self.assertEqual(env["NAGIENT_GIT_USERNAME"], "ddwnbot")
                self.assertEqual(env["NAGIENT_GIT_PASSWORD"], "ghp_demo")
                self.assertTrue(Path(env["GIT_ASKPASS"]).exists())
                self.assertEqual(cleanup_paths, [Path(env["GIT_ASKPASS"])])
            finally:
                for path in cleanup_paths:
                    path.unlink(missing_ok=True)

    def test_system_jobs_schedule_once_accepts_delay_seconds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            container = _container_with_workspace(Path(temp_dir))

            result = container.tool_service.invoke(
                ToolExecutionRequest(
                    tool_id="system_jobs",
                    function_name="system.jobs.schedule_once",
                    arguments={
                        "delay_seconds": 10,
                        "message": "check VS Code",
                        "transport_id": "telegram",
                        "session_id": "telegram:demo",
                        "approval_context": {"expected_by_user": True},
                    },
                )
            )

            self.assertEqual(result.status, "success")
            self.assertRegex(
                str(result.output["run_at"]),
                r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
            )

            list_result = container.tool_service.invoke(
                ToolExecutionRequest(
                    tool_id="system_jobs",
                    function_name="system.jobs.list",
                    arguments={},
                )
            )

            self.assertEqual(list_result.status, "success")
            jobs = list_result.output["jobs"]
            self.assertIsInstance(jobs, list)
            self.assertEqual(len(jobs), 1)
            self.assertIn("due_in_seconds", jobs[0])
            self.assertNotIn("payload", jobs[0])
            self.assertNotIn("notes", jobs[0])



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
        'root = "@home/workspace"',
        f'root = "{workspace_root}"',
    )
    config_file.write_text(config, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
