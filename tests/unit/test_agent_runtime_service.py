from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from nagient.app.configuration import load_runtime_configuration
from nagient.app.container import build_container
from nagient.app.settings import Settings
from nagient.application.services.transport_router_service import TransportRouterService
from nagient.domain.entities.agent_runtime import (
    AssistantResponse,
    NormalizedToolCall,
    NotificationIntent,
)
from nagient.domain.entities.tooling import ToolExecutionRequest
from nagient.infrastructure.logging import RuntimeLogger
from nagient.plugins.registry import TransportPluginRegistry
from nagient.providers.http import ProviderHttpError


class AgentRuntimeServiceTests(unittest.TestCase):
    def test_runtime_executes_tool_calls_and_returns_follow_up_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)
            _set_workspace_root(settings.config_file, workspace_root)

            object.__setattr__(
                container.provider_service,
                "generate_assistant_response",
                Mock(
                    side_effect=[
                        AssistantResponse(
                            message="Writing the reminder file.",
                            tool_calls=[
                                NormalizedToolCall(
                                    call_id="call-1",
                                    request=ToolExecutionRequest(
                                        tool_id="workspace_fs",
                                        function_name="workspace.fs.write_text",
                                        arguments={
                                            "path": "reminder.txt",
                                            "content": "scheduled",
                                        },
                                    ),
                                )
                            ],
                        ),
                        AssistantResponse(message="Done, the file is ready."),
                    ]
                ),
            )

            reply = container.agent_runtime_service.handle_inbound_event(
                "console",
                {
                    "event_type": "message",
                    "session_id": "console:demo",
                    "text": "Create a reminder file",
                },
            )

            self.assertEqual(reply, "Done, the file is ready.")
            self.assertEqual(
                (workspace_root / "reminder.txt").read_text(encoding="utf-8"),
                "scheduled",
            )

    def test_runtime_system_prompt_always_includes_runtime_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)
            runtime_config = load_runtime_configuration(settings)

            system_prompt = container.agent_runtime_service._system_prompt(  # noqa: SLF001
                runtime_config,
            )

            self.assertIn("modular agent runtime assistant", system_prompt)
            self.assertIn("run shell commands", system_prompt)
            self.assertIn("route outbound messages", system_prompt)
            self.assertIn("Any shell command must be finite and bounded", system_prompt)

    def test_runtime_handles_edited_messages_and_dispatches_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)
            _set_workspace_root(settings.config_file, workspace_root)

            router = TransportRouterService(
                settings=settings,
                plugin_registry=TransportPluginRegistry(),
                logger=RuntimeLogger(settings, "router-test"),
            )
            router.send_notification = Mock(  # type: ignore[method-assign]
                return_value={"status": "sent"}
            )
            container.agent_runtime_service.transport_router = router
            object.__setattr__(
                container.provider_service,
                "generate_assistant_response",
                Mock(
                    return_value=AssistantResponse(
                        message="Updated and notified.",
                        notifications=[
                            NotificationIntent(
                                level="info",
                                message="Outbound sync complete.",
                                transport_id="console",
                            )
                        ],
                    )
                ),
            )

            reply = container.agent_runtime_service.handle_inbound_event(
                "console",
                {
                    "event_type": "edited_message",
                    "session_id": "console:demo",
                    "text": "Updated request",
                },
            )

            self.assertEqual(reply, "Updated and notified.")
            router.send_notification.assert_called_once_with(
                transport_id="console",
                payload={"text": "Outbound sync complete.", "level": "info"},
            )

    def test_runtime_returns_friendly_timeout_after_tool_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)
            _set_workspace_root(settings.config_file, workspace_root)

            object.__setattr__(
                container.provider_service,
                "generate_assistant_response",
                Mock(
                    side_effect=[
                        AssistantResponse(
                            message="Running the command.",
                            tool_calls=[
                                NormalizedToolCall(
                                    call_id="call-1",
                                    request=ToolExecutionRequest(
                                        tool_id="workspace_shell",
                                        function_name="workspace.shell.run",
                                        arguments={
                                            "command": "printf done",
                                            "read_only": True,
                                        },
                                    ),
                                )
                            ],
                        ),
                        ProviderHttpError(
                            "Timed out while waiting for https://example.test/responses: "
                            "The read operation timed out"
                        ),
                    ]
                ),
            )

            reply = container.agent_runtime_service.handle_inbound_event(
                "console",
                {
                    "event_type": "message",
                    "session_id": "console:demo",
                    "text": "Run a quick command",
                },
            )

            self.assertIsNotNone(reply)
            self.assertIn("Running the command.", reply or "")
            self.assertIn("Latest tool result: workspace.shell.run (success).", reply or "")
            self.assertIn("stdout:\ndone", reply or "")

    def test_runtime_returns_friendly_timeout_before_tool_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)
            _set_workspace_root(settings.config_file, workspace_root)

            object.__setattr__(
                container.provider_service,
                "generate_assistant_response",
                Mock(
                    side_effect=ProviderHttpError(
                        "Timed out while waiting for https://example.test/responses: "
                        "The read operation timed out"
                    )
                ),
            )

            reply = container.agent_runtime_service.handle_inbound_event(
                "console",
                {
                    "event_type": "message",
                    "session_id": "console:demo",
                    "text": "Say hello",
                },
            )

            self.assertEqual(
                reply,
                "Provider request timed out before the runtime could finish this turn. "
                "Retry the request or increase the provider timeout.",
            )


def _set_workspace_root(config_file: Path, workspace_root: Path) -> None:
    config = config_file.read_text(encoding="utf-8").replace(
        'root = ""',
        f'root = "{workspace_root}"',
    )
    config_file.write_text(config, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
