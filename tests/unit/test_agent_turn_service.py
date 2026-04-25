from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nagient.app.container import build_container
from nagient.app.settings import Settings
from nagient.domain.entities.agent_runtime import (
    AgentTurnContext,
    AgentTurnRequest,
    AssistantResponse,
    NormalizedToolCall,
)
from nagient.domain.entities.security import InteractionRequest, PostSubmitAction
from nagient.domain.entities.tooling import ToolExecutionRequest


class AgentTurnServiceTests(unittest.TestCase):
    def test_run_turn_executes_tool_batch_and_persists_interaction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)
            _set_workspace_root(settings.config_file, workspace_root)

            request = AgentTurnRequest(
                request_id="turn-1",
                user_message="Write a note and request a secret.",
                context=AgentTurnContext(
                    session_id="session-1",
                    transport_id="console",
                ),
                assistant_response=AssistantResponse(
                    message="Working on it.",
                    tool_calls=[
                        NormalizedToolCall(
                            call_id="call-1",
                            request=ToolExecutionRequest(
                                tool_id="workspace_fs",
                                function_name="workspace.fs.write_text",
                                arguments={"path": "note.txt", "content": "hello"},
                            ),
                        )
                    ],
                    interaction_requests=[
                        InteractionRequest(
                            request_id="",
                            session_id="session-1",
                            transport_id="console",
                            interaction_type="secret_input",
                            prompt="Enter token",
                            status="pending",
                            created_at="",
                            post_submit_actions=[
                                PostSubmitAction(
                                    action_type="secret.store",
                                    payload={"secret_name": "GITHUB_TOKEN", "scope": "tool"},
                                )
                            ],
                        )
                    ],
                ),
            )

            result = container.agent_turn_service.run_turn(request)

            self.assertEqual(result.message, "Working on it.")
            self.assertEqual(result.tool_results[0].status, "success")
            self.assertTrue((workspace_root / "note.txt").exists())
            self.assertEqual(len(result.interaction_requests), 1)
            self.assertEqual(result.interaction_requests[0].status, "pending")
            self.assertIsNotNone(result.checkpoint_id)


def _set_workspace_root(config_file: Path, workspace_root: Path) -> None:
    config = config_file.read_text(encoding="utf-8").replace(
        'root = ""',
        f'root = "{workspace_root}"',
    )
    config_file.write_text(config, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
