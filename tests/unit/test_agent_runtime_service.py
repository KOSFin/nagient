from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock

from nagient.app.configuration import load_runtime_configuration
from nagient.app.container import build_container
from nagient.app.settings import Settings
from nagient.application.services.agent_runtime_service import _streamed_message_preview
from nagient.application.services.transport_router_service import TransportRouterService
from nagient.domain.entities.agent_runtime import (
    AssistantResponse,
    NormalizedToolCall,
    NotificationIntent,
)
from nagient.domain.entities.jobs import JobRecord
from nagient.domain.entities.tooling import ToolExecutionRequest
from nagient.infrastructure.logging import RuntimeLogger
from nagient.plugins.registry import TransportPluginRegistry
from nagient.providers.http import ProviderHttpError


class _RecordingTransportRouter:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict[str, object]]] = []
        self.custom_calls: list[tuple[str, str, dict[str, object]]] = []
        self.typing: list[tuple[str, dict[str, object]]] = []

    def send_message(
        self,
        *,
        transport_id: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        self.messages.append((transport_id, dict(payload)))
        return {"status": "sent", "message_id": "approval-message"}

    def send_typing(
        self,
        *,
        transport_id: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        self.typing.append((transport_id, dict(payload)))
        return {"status": "sent"}

    def invoke_custom(
        self,
        *,
        transport_id: str,
        function_name: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        self.custom_calls.append((transport_id, function_name, dict(payload)))
        return {"status": "ok"}

    def supports_interaction(self, *, transport_id: str, capability: str) -> bool:
        del transport_id
        return capability in {"approval.inline", "approval.callback"}

    def interaction_function(self, *, transport_id: str, capability: str) -> str | None:
        del transport_id
        return {
            "approval.callback.answer": "nagient.telegram.answerCallback",
            "approval.callback.edit": "nagient.telegram.editMessage",
        }.get(capability)


class AgentRuntimeServiceTests(unittest.TestCase):
    def test_stream_preview_decodes_an_unclosed_json_message(self) -> None:
        self.assertEqual(
            _streamed_message_preview('{"message":"Privet\\n\\u041c"'),
            "Privet\nМ",
        )
        self.assertEqual(
            _streamed_message_preview('{ "message" : "partial \\"quote"'),
            'partial "quote',
        )

    def test_runtime_can_send_deferred_tool_reply_without_follow_up(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)
            _set_workspace_root(settings.config_file, workspace_root)

            provider_mock = Mock(
                return_value=AssistantResponse(
                    message="Вот вывод команды:\n{{tool:call-1.output.stdout}}",
                    message_mode="after_tools",
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
                )
            )
            object.__setattr__(
                container.provider_service,
                "generate_assistant_response",
                provider_mock,
            )

            reply = container.agent_runtime_service.handle_inbound_event(
                "console",
                {
                    "event_type": "message",
                    "session_id": "console:demo",
                    "text": "Покажи лог команды",
                },
            )

            self.assertEqual(reply, "Вот вывод команды:\ndone")
            self.assertEqual(provider_mock.call_count, 1)

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
            self.assertIn("approval_context", system_prompt)

    def test_runtime_tool_catalog_keeps_external_github_api_disabled_by_default(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)
            runtime_config = load_runtime_configuration(settings)

            catalog = container.agent_runtime_service._tool_catalog(  # noqa: SLF001
                runtime_config
            )
            functions = {
                str(item["function_name"]): item
                for item in catalog
                if isinstance(item.get("function_name"), str)
            }

            self.assertEqual(
                functions["workspace.git.status"]["tool_id"],
                "workspace_git",
            )
            self.assertNotIn("nagient.github_api.get_authenticated_user", functions)
            self.assertEqual(
                functions["system.config.read"]["tool_id"],
                "system_config",
            )
            self.assertEqual(
                functions["system.config.patch"]["tool_id"],
                "system_config",
            )
            self.assertEqual(
                functions["system.jobs.schedule_message"]["tool_id"],
                "system_jobs",
            )
            self.assertEqual(
                functions["system.jobs.schedule_tool"]["tool_id"],
                "system_jobs",
            )
            git_run_schema = functions["workspace.git.run"]["input_schema"]
            self.assertIsInstance(git_run_schema, dict)
            properties = git_run_schema.get("properties")
            self.assertIsInstance(properties, dict)
            self.assertIn("approval_context", properties)
            config_patch_schema = functions["system.config.patch"]["input_schema"]
            self.assertIsInstance(config_patch_schema, dict)
            config_patch_properties = config_patch_schema.get("properties")
            self.assertIsInstance(config_patch_properties, dict)
            self.assertIn("approval_context", config_patch_properties)

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

    def test_runtime_returns_recent_tool_results_when_follow_up_provider_fails(self) -> None:
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
                            message="Trying both actions.",
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
                                ),
                                NormalizedToolCall(
                                    call_id="call-2",
                                    request=ToolExecutionRequest(
                                        tool_id="workspace_shell",
                                        function_name="workspace.shell.run",
                                        arguments={
                                            "command": "printf done",
                                            "read_only": True,
                                        },
                                    ),
                                ),
                            ],
                        ),
                        ProviderHttpError("Remote end closed connection without response"),
                    ]
                ),
            )

            reply = container.agent_runtime_service.handle_inbound_event(
                "console",
                {
                    "event_type": "message",
                    "session_id": "console:demo",
                    "text": "Do two quick checks",
                },
            )

            self.assertIsNotNone(reply)
            self.assertIn("Recent tool results:", reply or "")
            self.assertIn("workspace.fs.write_text (success).", reply or "")
            self.assertIn("workspace.shell.run (success).", reply or "")

    def test_provider_runtime_log_writes_file_without_echoing_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                container.agent_runtime_service._provider_runtime_log(  # noqa: SLF001
                    "Provider demo: hidden from interactive chat"
                )

            self.assertEqual(stdout.getvalue(), "")
            runtime_log = (settings.log_dir / "runtime.log").read_text(encoding="utf-8")
            self.assertIn("Provider demo: hidden from interactive chat", runtime_log)

    def test_transport_approve_executes_pending_tool_action_and_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            target_path = workspace_root / "old.txt"
            target_path.write_text("remove me", encoding="utf-8")
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)
            _set_workspace_root(settings.config_file, workspace_root)

            provider_mock = Mock(
                side_effect=[
                    AssistantResponse(
                        message="I'll remove it after approval.",
                        tool_calls=[
                            NormalizedToolCall(
                                call_id="call-1",
                                request=ToolExecutionRequest(
                                    tool_id="workspace_fs",
                                    function_name="workspace.fs.delete",
                                    arguments={
                                        "path": "old.txt",
                                        "approval_context": {
                                            "on_success": "resume_model",
                                        },
                                    },
                                ),
                            )
                        ],
                    ),
                    AssistantResponse(message="Готово, файл удален."),
                ]
            )
            object.__setattr__(
                container.provider_service,
                "generate_assistant_response",
                provider_mock,
            )

            first_reply = container.agent_runtime_service.handle_inbound_event(
                "telegram",
                {
                    "event_type": "message",
                    "session_id": "telegram:demo",
                    "text": "удали old.txt",
                },
            )

            self.assertIsNotNone(first_reply)
            self.assertIn("Нужно подтверждение", first_reply or "")
            self.assertTrue(target_path.exists())

            approval_reply = container.agent_runtime_service.handle_inbound_event(
                "telegram",
                {
                    "event_type": "message",
                    "session_id": "telegram:demo",
                    "text": "approve",
                },
            )

            self.assertEqual(approval_reply, "Готово, файл удален.")
            self.assertFalse(target_path.exists())
            self.assertEqual(provider_mock.call_count, 2)
            runtime_log = (settings.log_dir / "runtime.log").read_text(encoding="utf-8")
            self.assertIn("Waiting for approval", runtime_log)
            self.assertIn("Resolved approval", runtime_log)

    def test_transport_approve_can_use_success_message_without_model_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            target_path = workspace_root / "old.txt"
            target_path.write_text("remove me", encoding="utf-8")
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)
            _set_workspace_root(settings.config_file, workspace_root)

            provider_mock = Mock(
                return_value=AssistantResponse(
                    message="I'll remove it after approval.",
                    tool_calls=[
                        NormalizedToolCall(
                            call_id="call-1",
                            request=ToolExecutionRequest(
                                tool_id="workspace_fs",
                                function_name="workspace.fs.delete",
                                arguments={
                                    "path": "old.txt",
                                    "approval_context": {
                                        "on_success": "message",
                                        "on_success_message": "Готово, old.txt удален.",
                                    },
                                },
                            ),
                        )
                    ],
                )
            )
            object.__setattr__(
                container.provider_service,
                "generate_assistant_response",
                provider_mock,
            )

            container.agent_runtime_service.handle_inbound_event(
                "telegram",
                {
                    "event_type": "message",
                    "session_id": "telegram:demo",
                    "text": "удали old.txt",
                },
            )
            approval_reply = container.agent_runtime_service.handle_inbound_event(
                "telegram",
                {
                    "event_type": "message",
                    "session_id": "telegram:demo",
                    "text": "approve",
                },
            )

            self.assertEqual(approval_reply, "Готово, old.txt удален.")
            self.assertFalse(target_path.exists())
            self.assertEqual(provider_mock.call_count, 1)

    def test_telegram_approval_prompt_uses_inline_buttons(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            target_path = workspace_root / "old.txt"
            target_path.write_text("remove me", encoding="utf-8")
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)
            _set_workspace_root(settings.config_file, workspace_root)

            router = _RecordingTransportRouter()
            container.agent_runtime_service.transport_router = router
            object.__setattr__(
                container.provider_service,
                "generate_assistant_response",
                Mock(
                    return_value=AssistantResponse(
                        message="I'll remove it after approval.",
                        tool_calls=[
                            NormalizedToolCall(
                                call_id="call-1",
                                request=ToolExecutionRequest(
                                    tool_id="workspace_fs",
                                    function_name="workspace.fs.delete",
                                    arguments={
                                        "path": "old.txt",
                                        "approval_context": {
                                            "on_success": "message",
                                            "on_success_message": "Готово.",
                                        },
                                    },
                                ),
                            )
                        ],
                    )
                ),
            )

            reply = container.agent_runtime_service.handle_inbound_event(
                "telegram",
                {
                    "event_type": "message",
                    "session_id": "telegram:demo",
                    "text": "удали old.txt",
                    "reply_target": {"chat_id": "1522105862"},
                },
            )

            self.assertIsNone(reply)
            self.assertTrue(target_path.exists())
            self.assertEqual(len(router.messages), 1)
            payload = router.messages[0][1]
            self.assertIn("Нужно подтверждение", str(payload["text"]))
            keyboard = payload["reply_markup"]
            assert isinstance(keyboard, dict)
            inline_keyboard = keyboard["inline_keyboard"]
            assert isinstance(inline_keyboard, list)
            first_row = inline_keyboard[0]
            assert isinstance(first_row, list)
            first_button = first_row[0]
            assert isinstance(first_button, dict)
            callback_data = first_button["callback_data"]
            self.assertTrue(str(callback_data).startswith("nagient:approval:"))

    def test_telegram_approval_callback_resolves_specific_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            target_path = workspace_root / "old.txt"
            target_path.write_text("remove me", encoding="utf-8")
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)
            _set_workspace_root(settings.config_file, workspace_root)

            router = _RecordingTransportRouter()
            container.agent_runtime_service.transport_router = router
            object.__setattr__(
                container.provider_service,
                "generate_assistant_response",
                Mock(
                    return_value=AssistantResponse(
                        message="I'll remove it after approval.",
                        tool_calls=[
                            NormalizedToolCall(
                                call_id="call-1",
                                request=ToolExecutionRequest(
                                    tool_id="workspace_fs",
                                    function_name="workspace.fs.delete",
                                    arguments={
                                        "path": "old.txt",
                                        "approval_context": {
                                            "on_success": "message",
                                            "on_success_message": "Готово.",
                                        },
                                    },
                                ),
                            )
                        ],
                    )
                ),
            )

            container.agent_runtime_service.handle_inbound_event(
                "telegram",
                {
                    "event_type": "message",
                    "session_id": "telegram:demo",
                    "text": "удали old.txt",
                    "reply_target": {"chat_id": "1522105862"},
                },
            )
            keyboard = router.messages[0][1]["reply_markup"]
            assert isinstance(keyboard, dict)
            inline_keyboard = keyboard["inline_keyboard"]
            assert isinstance(inline_keyboard, list)
            first_row = inline_keyboard[0]
            assert isinstance(first_row, list)
            first_button = first_row[0]
            assert isinstance(first_button, dict)
            callback_data = first_button["callback_data"]

            callback_reply = container.agent_runtime_service.handle_inbound_event(
                "telegram",
                {
                    "event_type": "callback_query",
                    "session_id": "telegram:demo",
                    "text": callback_data,
                    "reply_target": {"chat_id": "1522105862"},
                    "callback_query_id": "callback-1",
                    "message_id": "approval-message",
                },
            )

            self.assertIsNone(callback_reply)
            self.assertFalse(target_path.exists())
            function_names = [item[1] for item in router.custom_calls]
            self.assertIn("nagient.telegram.answerCallback", function_names)
            self.assertIn("nagient.telegram.editMessage", function_names)

    def test_scheduled_wake_sends_reply_through_transport_router(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)
            _set_workspace_root(settings.config_file, workspace_root)

            router = _RecordingTransportRouter()
            container.agent_runtime_service.transport_router = router
            object.__setattr__(
                container.provider_service,
                "generate_assistant_response",
                Mock(return_value=AssistantResponse(message="Проверь VS Code.")),
            )

            reply = container.agent_runtime_service.handle_scheduled_job(
                JobRecord(
                    job_id="job_demo",
                    name="reminder",
                    status="scheduled",
                    trigger="once",
                    created_at="2026-06-07T13:00:00Z",
                    payload={
                        "action_type": "agent.wake",
                        "session_id": "telegram:1522105862",
                        "transport_id": "telegram",
                        "message": "напомни проверить VS Code",
                    },
                )
            )

            self.assertIsNone(reply)
            self.assertEqual(router.messages[0][0], "telegram")
            self.assertEqual(router.messages[0][1]["chat_id"], "1522105862")
            self.assertEqual(router.messages[0][1]["text"], "Проверь VS Code.")

    def test_scheduled_message_sends_without_waking_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)
            _set_workspace_root(settings.config_file, workspace_root)

            router = _RecordingTransportRouter()
            container.agent_runtime_service.transport_router = router
            provider_mock = Mock(side_effect=AssertionError("provider should not run"))
            object.__setattr__(
                container.provider_service,
                "generate_assistant_response",
                provider_mock,
            )

            reply = container.agent_runtime_service.handle_scheduled_job(
                JobRecord(
                    job_id="job_message",
                    name="message",
                    status="scheduled",
                    trigger="once",
                    created_at="2026-06-07T13:00:00Z",
                    payload={
                        "action_type": "transport.send_message",
                        "session_id": "telegram:1522105862",
                        "transport_id": "telegram",
                        "text": "Пора проверить VS Code.",
                    },
                )
            )

            self.assertIsNone(reply)
            provider_mock.assert_not_called()
            self.assertEqual(router.messages[0][0], "telegram")
            self.assertEqual(router.messages[0][1]["chat_id"], "1522105862")
            self.assertEqual(router.messages[0][1]["text"], "Пора проверить VS Code.")

    def test_scheduled_tool_executes_exact_request_without_waking_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)
            _set_workspace_root(settings.config_file, workspace_root)

            router = _RecordingTransportRouter()
            container.agent_runtime_service.transport_router = router
            provider_mock = Mock(side_effect=AssertionError("provider should not run"))
            object.__setattr__(
                container.provider_service,
                "generate_assistant_response",
                provider_mock,
            )

            reply = container.agent_runtime_service.handle_scheduled_job(
                JobRecord(
                    job_id="job_tool",
                    name="write file",
                    status="scheduled",
                    trigger="once",
                    created_at="2026-06-07T13:00:00Z",
                    payload={
                        "action_type": "tool.invoke",
                        "session_id": "telegram:1522105862",
                        "transport_id": "telegram",
                        "success_message": "Файл записан.",
                        "tool_request": {
                            "tool_id": "workspace_fs",
                            "function_name": "workspace.fs.write_text",
                            "arguments": {
                                "path": "scheduled.txt",
                                "content": "done",
                            },
                        },
                    },
                )
            )

            self.assertIsNone(reply)
            provider_mock.assert_not_called()
            self.assertEqual((workspace_root / "scheduled.txt").read_text(), "done")
            self.assertEqual(router.messages[0][1]["text"], "Файл записан.")

    def test_progress_mode_sends_assistant_status_before_tool_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)
            _set_workspace_root(settings.config_file, workspace_root)
            container.configuration_service.configure_agent(
                {"progress": {"enabled": True}}
            )

            router = _RecordingTransportRouter()
            container.agent_runtime_service.transport_router = router
            object.__setattr__(
                container.provider_service,
                "generate_assistant_response",
                Mock(
                    side_effect=[
                        AssistantResponse(
                            message="Начинаю: сейчас выполню команду.",
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
                        AssistantResponse(message="Готово."),
                    ]
                ),
            )

            reply = container.agent_runtime_service.handle_inbound_event(
                "telegram",
                {
                    "event_type": "message",
                    "session_id": "telegram:demo",
                    "text": "выполни команду",
                    "reply_target": {"chat_id": "1522105862"},
                },
            )

            self.assertEqual(reply, "Готово.")
            self.assertEqual(router.messages[0][0], "telegram")
            self.assertEqual(
                router.messages[0][1]["text"],
                "Начинаю: сейчас выполню команду.",
            )

    def test_runtime_finalizes_with_summary_when_max_turns_reached(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)
            _set_workspace_root(settings.config_file, workspace_root)
            container.configuration_service.configure_agent({"max_turns": 2})

            def _tool_step(message: str) -> AssistantResponse:
                return AssistantResponse(
                    message=message,
                    tool_calls=[
                        NormalizedToolCall(
                            call_id="call-1",
                            request=ToolExecutionRequest(
                                tool_id="workspace_shell",
                                function_name="workspace.shell.run",
                                arguments={"command": "printf step", "read_only": True},
                            ),
                        )
                    ],
                )

            provider_mock = Mock(
                side_effect=[
                    _tool_step("Шаг 1: собираю данные."),
                    _tool_step("Шаг 2: продолжаю собирать."),
                    AssistantResponse(message="Итог: задача выполнена, вот результат."),
                ]
            )
            object.__setattr__(
                container.provider_service,
                "generate_assistant_response",
                provider_mock,
            )

            reply = container.agent_runtime_service.handle_inbound_event(
                "console",
                {
                    "event_type": "message",
                    "session_id": "console:demo",
                    "text": "Выполни многошаговую задачу",
                },
            )

            # Two tool turns exhaust max_turns, then a third summary-only call
            # composes the real answer instead of returning the mid-plan message.
            self.assertEqual(reply, "Итог: задача выполнена, вот результат.")
            self.assertEqual(provider_mock.call_count, 3)
            final_call = provider_mock.call_args_list[-1]
            self.assertEqual(final_call.kwargs["tool_catalog"], [])
            runtime_log = (settings.log_dir / "runtime.log").read_text(encoding="utf-8")
            self.assertIn("Reached max_turns", runtime_log)

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
                "This is the model/provider timeout, not a tool timeout. "
                "Retry the request or increase the provider timeout.",
            )


def _set_workspace_root(config_file: Path, workspace_root: Path) -> None:
    config = config_file.read_text(encoding="utf-8").replace(
        'root = "@home/workspace"',
        f'root = "{workspace_root}"',
    )
    config_file.write_text(config, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
