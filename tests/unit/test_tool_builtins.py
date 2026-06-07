from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from nagient.app.container import build_container
from nagient.app.settings import Settings
from nagient.domain.entities.tooling import ToolExecutionRequest
from nagient.tools.base import ToolExecutionContext
from nagient.tools.builtin import GitHubApiToolPlugin, _plan_shell_command


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

    def test_github_api_tool_uses_structured_requests(self) -> None:
        seen: dict[str, object] = {}
        responses = [
            (
                b'{"number": 7, "title": "Bug", "state": "open", '
                b'"html_url": "https://github.test/acme/repo/issues/7"}'
            ),
            (
                b'{"login": "octo", "id": 42, "name": "Octo", '
                b'"html_url": "https://github.test/octo", "type": "User"}'
            ),
            (
                b'[{"full_name": "octo/repo", "private": false, '
                b'"default_branch": "main", "html_url": "https://github.test/octo/repo"}]'
            ),
        ]

        class _Response:
            def __enter__(self) -> object:
                return self

            def __exit__(self, exc_type: object, exc: object, tb: object) -> object:
                return None

            def read(self) -> bytes:
                return responses.pop(0)

        def _opener(request: object, timeout: float = 15.0) -> _Response:
            seen["url"] = request.full_url
            seen["method"] = request.get_method()
            seen["data"] = request.data
            seen["timeout"] = timeout
            return _Response()

        plugin = GitHubApiToolPlugin(opener=_opener)
        context = _tool_context(
            config={
                "token_secret": "GITHUB_TOKEN",
                "base_url": "https://github.test/api/v3",
                "timeout_seconds": 3,
            },
            secret_value="ghp_secret",
        )

        result = plugin.create_issue(
            {
                "owner": "acme",
                "repo": "repo",
                "title": "Bug",
                "body": "Details",
            },
            context,
        )

        self.assertEqual(result["number"], 7)
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(seen["url"], "https://github.test/api/v3/repos/acme/repo/issues")
        self.assertEqual(seen["timeout"], 3.0)
        self.assertIn(b'"title": "Bug"', seen["data"])

        user = plugin.get_authenticated_user({}, context)
        self.assertEqual(user["login"], "octo")
        self.assertEqual(seen["method"], "GET")
        self.assertEqual(seen["url"], "https://github.test/api/v3/user")

        repositories = plugin.list_repositories({"per_page": 1}, context)
        self.assertEqual(repositories["repositories"][0]["full_name"], "octo/repo")
        self.assertEqual(
            seen["url"],
            "https://github.test/api/v3/user/repos?per_page=1",
        )

        dry_run = plugin.add_issue_comment(
            {
                "owner": "acme",
                "repo": "repo",
                "issue_number": 7,
                "body": "Thanks",
            },
            _tool_context(
                config={"base_url": "https://api.github.com"},
                secret_value="ghp_secret",
                dry_run=True,
            ),
        )
        self.assertTrue(dry_run["dry_run"])
        self.assertEqual(dry_run["method"], "POST")


def _container_with_workspace(root: Path) -> object:
    home_dir = root / "home"
    workspace_root = root / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
    container = build_container(settings)
    container.configuration_service.initialize(force=True)
    _set_workspace_root(settings.config_file, workspace_root)
    return container


def _tool_context(
    *,
    config: dict[str, object],
    secret_value: str,
    dry_run: bool = False,
) -> ToolExecutionContext:
    root = Path("/tmp/nagient-workspace")
    secret_broker = SimpleNamespace(
        resolve_secret=lambda name, scope_hint=None: secret_value,
    )
    return ToolExecutionContext(
        settings=SimpleNamespace(),
        workspace=SimpleNamespace(
            root=root,
            mode="bounded",
            metadata=SimpleNamespace(workspace_id="workspace-1"),
        ),
        workspace_manager=SimpleNamespace(),
        tool_id="github_api",
        plugin_id="github.api",
        config=config,
        secret_broker=secret_broker,
        backup_manager=SimpleNamespace(),
        request_interaction=lambda request: request,
        request_approval=lambda request: request,
        invoke_reconcile=lambda: {},
        invoke_assistant_resume=lambda response: {},
        dry_run=dry_run,
    )


def _set_workspace_root(config_file: Path, workspace_root: Path) -> None:
    config = config_file.read_text(encoding="utf-8").replace(
        'root = "@home/workspace"',
        f'root = "{workspace_root}"',
    )
    config_file.write_text(config, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
