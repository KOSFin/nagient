from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nagient.app.container import build_container
from nagient.app.settings import Settings
from nagient.domain.entities.tooling import ToolExecutionRequest


class ToolServiceTests(unittest.TestCase):
    def test_workspace_write_read_and_delete_requires_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)
            _set_workspace_root(settings.config_file, workspace_root)

            write_result = container.tool_service.invoke(
                ToolExecutionRequest(
                    tool_id="workspace_fs",
                    function_name="workspace.fs.write_text",
                    arguments={"path": "note.txt", "content": "hello"},
                )
            )
            self.assertEqual(write_result.status, "success")
            self.assertEqual(
                (workspace_root / "note.txt").read_text(encoding="utf-8"),
                "hello",
            )

            read_result = container.tool_service.invoke(
                ToolExecutionRequest(
                    tool_id="workspace_fs",
                    function_name="workspace.fs.read_text",
                    arguments={"path": "note.txt"},
                )
            )
            self.assertEqual(read_result.output["content"], "hello")

            delete_result = container.tool_service.invoke(
                ToolExecutionRequest(
                    tool_id="workspace_fs",
                    function_name="workspace.fs.delete",
                    arguments={"path": "note.txt"},
                )
            )
            self.assertEqual(delete_result.status, "approval_required")
            self.assertIsNotNone(delete_result.approval_request_id)

            approval_result = container.workflow_service.resolve_approval(
                delete_result.approval_request_id,
                "approve",
            )
            self.assertEqual(approval_result.status, "approved")
            self.assertFalse((workspace_root / "note.txt").exists())

    def test_secure_interaction_submission_stores_tool_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)
            _set_workspace_root(settings.config_file, workspace_root)

            request_result = container.tool_service.invoke(
                ToolExecutionRequest(
                    tool_id="transport_interaction",
                    function_name="transport.interaction.request",
                    arguments={
                        "prompt": "Enter GitHub token",
                        "interaction_type": "secret_input",
                        "post_submit_actions": [
                            {
                                "action_type": "secret.store",
                                "payload": {
                                    "secret_name": "GITHUB_TOKEN",
                                    "scope": "tool",
                                },
                            }
                        ],
                    },
                )
            )
            self.assertEqual(request_result.status, "success")
            request_id = str(request_result.output["request_id"])

            interaction_result = container.workflow_service.submit_interaction(
                request_id,
                response="ghs-secret",
            )
            self.assertEqual(interaction_result.status, "success")
            self.assertEqual(
                container.secret_broker.resolve_secret("GITHUB_TOKEN", scope_hint="tool"),
                "ghs-secret",
            )


def _set_workspace_root(config_file: Path, workspace_root: Path) -> None:
    config = config_file.read_text(encoding="utf-8").replace(
        'root = ""',
        f'root = "{workspace_root}"',
    )
    config_file.write_text(config, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
