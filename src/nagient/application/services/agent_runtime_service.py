from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from typing import Any

from nagient.app.configuration import RuntimeConfiguration, load_runtime_configuration
from nagient.app.settings import Settings
from nagient.domain.entities.agent_runtime import (
    AgentTurnContext,
    AgentTurnRequest,
    AssistantResponse,
    ConfigMutationIntent,
    NotificationIntent,
)
from nagient.domain.entities.jobs import JobRecord
from nagient.domain.entities.tooling import ToolExecutionResult
from nagient.infrastructure.logging import RuntimeLogger, write_runtime_log
from nagient.tools.registry import ToolPluginRegistry
from nagient.workspace.manager import WorkspaceManager

_TOOL_PLACEHOLDER_RE = re.compile(
    r"\{\{tool:(?P<call_id>[^.}]+)\.(?P<path>[A-Za-z0-9_.-]+)\}\}"
)


@dataclass
class AgentRuntimeService:
    settings: Settings
    workspace_manager: WorkspaceManager
    memory_service: Any
    provider_service: Any
    agent_turn_service: Any
    tool_registry: ToolPluginRegistry
    logger: RuntimeLogger
    transport_router: Any | None = None

    def handle_inbound_event(
        self,
        transport_id: str,
        event: dict[str, object],
        *,
        provider_id: str | None = None,
        system_prompt_override: str | None = None,
    ) -> str | None:
        runtime_config = load_runtime_configuration(self.settings)
        layout = self.workspace_manager.ensure_layout(runtime_config.workspace)
        session_id = str(event.get("session_id", f"{transport_id}:default"))
        event_type = str(event.get("event_type", "message"))
        text = str(event.get("text", "")).strip()
        if event_type not in {"message", "edited_message", "callback_query", "system_wake"}:
            self.logger.debug(
                "agent_runtime.skip_event",
                "Skipped unsupported inbound event type.",
                transport_id=transport_id,
                session_id=session_id,
                event_type=event_type,
            )
            return None
        if not text:
            return None

        self.memory_service.append_message(
            layout,
            session_id=session_id,
            transport_id=transport_id,
            role="user",
            content=text,
            metadata=_event_metadata(event, event_type),
        )
        self._maybe_send_typing(transport_id=transport_id, event=event)

        previous_results: list[dict[str, object]] = []
        last_message: str | None = None
        for turn_index in range(runtime_config.agent.max_turns):
            retrieval_query = text if _should_retrieve(text) and turn_index == 0 else None
            prompt_context = self.memory_service.build_prompt_context(
                layout,
                session_id=session_id,
                config=runtime_config.agent.memory,
                retrieval_query=retrieval_query,
            )
            try:
                assistant_response = self.provider_service.generate_assistant_response(
                    message=text,
                    provider_id=provider_id,
                    session_id=session_id,
                    transport_id=transport_id,
                    system_prompt=self._system_prompt(
                        runtime_config,
                        override=system_prompt_override,
                    ),
                    prompt_context=prompt_context,
                    tool_catalog=self._tool_catalog(runtime_config),
                    transport_catalog=self._transport_catalog(),
                    previous_results=previous_results,
                    runtime_log=self._provider_runtime_log,
                )
            except Exception as exc:
                return self._finalize_provider_failure(
                    layout=layout,
                    session_id=session_id,
                    transport_id=transport_id,
                    turn_index=turn_index,
                    last_message=last_message,
                    previous_results=previous_results,
                    error=exc,
                )
            if assistant_response.message.strip():
                if not _should_defer_assistant_message(assistant_response):
                    last_message = assistant_response.message.strip()
                    self.memory_service.append_message(
                        layout,
                        session_id=session_id,
                        transport_id=transport_id,
                        role="assistant",
                        content=last_message,
                        metadata={"turn_index": turn_index},
                    )

            turn_result = self.agent_turn_service.run_turn(
                AgentTurnRequest(
                    request_id=f"{session_id}:{turn_index}",
                    user_message=text,
                    context=AgentTurnContext(
                        session_id=session_id,
                        transport_id=transport_id,
                        workspace_root=str(layout.root),
                        workspace_mode=layout.config.mode,
                        previous_results=previous_results,
                        metadata={"event_type": event_type},
                    ),
                    assistant_response=assistant_response,
                )
            )
            if turn_result.tool_results:
                for result in turn_result.tool_results:
                    self.memory_service.append_message(
                        layout,
                        session_id=session_id,
                        transport_id=transport_id,
                        role="tool",
                        content=json.dumps(result.to_dict(), ensure_ascii=False),
                        metadata={"function_name": result.function_name},
                    )

            deferred_reply = _render_deferred_assistant_message(
                assistant_response=assistant_response,
                tool_results=turn_result.tool_results,
            )
            if deferred_reply:
                last_message = deferred_reply
                self.memory_service.append_message(
                    layout,
                    session_id=session_id,
                    transport_id=transport_id,
                    role="assistant",
                    content=deferred_reply,
                    metadata={"turn_index": turn_index},
                )

            self.logger.info(
                "agent_runtime.turn_completed",
                "Completed agent runtime turn step.",
                session_id=session_id,
                transport_id=transport_id,
                step=turn_index,
                tool_results=len(turn_result.tool_results),
                approvals=len(turn_result.approval_requests),
                interactions=len(turn_result.interaction_requests),
            )
            if turn_result.notifications:
                self._dispatch_notifications(
                    default_transport_id=transport_id,
                    notifications=turn_result.notifications,
                )
            if turn_result.config_mutations:
                self._record_config_mutations(
                    session_id=session_id,
                    transport_id=transport_id,
                    mutations=turn_result.config_mutations,
                )

            if turn_result.approval_requests or turn_result.interaction_requests:
                return turn_result.message or last_message
            if not assistant_response.tool_calls:
                return turn_result.message or last_message
            if deferred_reply is not None:
                return deferred_reply

            previous_results = [result.to_dict() for result in turn_result.tool_results]
            text = "Continue the task using the latest tool results."

        self.logger.warning(
            "agent_runtime.max_turns_reached",
            "Agent runtime stopped after reaching max_turns.",
            session_id=session_id,
            transport_id=transport_id,
            max_turns=runtime_config.agent.max_turns,
        )
        return last_message

    def handle_scheduled_job(self, job: JobRecord) -> str | None:
        action_type = str(job.payload.get("action_type", "")).strip()
        if action_type != "agent.wake":
            self.logger.warning(
                "agent_runtime.skip_job",
                "Skipped unsupported scheduled job payload.",
                job_id=job.job_id,
                action_type=action_type or "unknown",
            )
            return None
        transport_id = str(job.payload.get("transport_id", "console")).strip() or "console"
        session_id = str(job.payload.get("session_id", "system")).strip() or "system"
        message = str(job.payload.get("message", "")).strip()
        if not message:
            return None
        return self.handle_inbound_event(
            transport_id,
            {
                "event_type": "system_wake",
                "session_id": session_id,
                "text": message,
            },
        )

    def _system_prompt(
        self,
        runtime_config: RuntimeConfiguration,
        *,
        override: str | None = None,
    ) -> str:
        prompt_parts: list[str] = []
        system_prompt_file = runtime_config.agent.system_prompt_file
        if system_prompt_file is not None and system_prompt_file.exists():
            prompt_parts.append(system_prompt_file.read_text(encoding="utf-8").strip())
        if override is not None and override.strip():
            prompt_parts.append(override.strip())
        prompt_parts.append(_runtime_identity_prompt())
        prompt_parts.append(
            "You must return strict JSON for the assistant response schema. "
            "Do not emit markdown fences unless the message field itself needs markdown."
        )
        return "\n\n".join(part for part in prompt_parts if part).strip()

    def _transport_catalog(self) -> list[dict[str, object]]:
        if self.transport_router is None:
            return []
        try:
            payload = self.transport_router.list_transports()
        except Exception as exc:
            self.logger.warning(
                "agent_runtime.transport_catalog_failed",
                "Failed to build transport catalog for the provider prompt.",
                error=str(exc),
            )
            return []
        return [item for item in payload if isinstance(item, dict)]

    def _tool_catalog(
        self,
        runtime_config: RuntimeConfiguration,
    ) -> list[dict[str, object]]:
        discovery = self.tool_registry.discover(self.settings.tools_dir)
        catalog: list[dict[str, object]] = []
        for tool in runtime_config.tools:
            if not tool.enabled:
                continue
            plugin = discovery.plugins.get(tool.plugin_id)
            if plugin is None:
                continue
            for function in plugin.manifest.functions:
                catalog.append(
                    {
                        "tool_id": tool.tool_id,
                        "plugin_id": tool.plugin_id,
                        "function_name": function.function_name,
                        "description": function.description,
                        "input_schema": function.input_schema,
                        "side_effect": function.side_effect,
                        "approval_policy": function.approval_policy,
                    }
                )
        return catalog

    def _dispatch_notifications(
        self,
        *,
        default_transport_id: str,
        notifications: list[NotificationIntent],
    ) -> None:
        if self.transport_router is None:
            return
        for notification in notifications:
            target_transport = notification.transport_id or default_transport_id
            payload = dict(notification.metadata)
            payload.setdefault("text", notification.message)
            payload.setdefault("level", notification.level)
            try:
                self.transport_router.send_notification(
                    transport_id=target_transport,
                    payload=payload,
                )
                self.logger.info(
                    "agent_runtime.notification_sent",
                    "Sent agent notification through transport router.",
                    transport_id=target_transport,
                    level=notification.level,
                )
            except Exception as exc:
                self.logger.warning(
                    "agent_runtime.notification_failed",
                    "Failed to send agent notification.",
                    transport_id=target_transport,
                    level=notification.level,
                    error=str(exc),
                )

    def _record_config_mutations(
        self,
        *,
        session_id: str,
        transport_id: str,
        mutations: list[ConfigMutationIntent],
    ) -> None:
        for mutation in mutations:
            self.logger.warning(
                "agent_runtime.config_mutation_requested",
                "Assistant requested a config mutation that still requires an explicit "
                "system workflow.",
                session_id=session_id,
                transport_id=transport_id,
                path=mutation.path,
                reason=mutation.reason,
            )

    def _maybe_send_typing(
        self,
        *,
        transport_id: str,
        event: dict[str, object],
    ) -> None:
        if self.transport_router is None or transport_id == "console":
            return
        reply_target = event.get("reply_target")
        if not isinstance(reply_target, dict) or not reply_target:
            return
        try:
            self.transport_router.send_typing(
                transport_id=transport_id,
                payload={str(key): value for key, value in reply_target.items()},
            )
        except Exception as exc:
            self.logger.debug(
                "agent_runtime.typing_skipped",
                "Could not send transport typing indicator.",
                transport_id=transport_id,
                error=str(exc),
            )

    def _finalize_provider_failure(
        self,
        *,
        layout: object,
        session_id: str,
        transport_id: str,
        turn_index: int,
        last_message: str | None,
        previous_results: list[dict[str, object]],
        error: Exception,
    ) -> str:
        reply = _provider_failure_reply(
            error=error,
            last_message=last_message,
            previous_results=previous_results,
        )
        self.logger.warning(
            "agent_runtime.provider_failed",
            "Provider request failed during an agent turn.",
            session_id=session_id,
            transport_id=transport_id,
            step=turn_index,
            error=str(error),
            previous_results=len(previous_results),
        )
        self.memory_service.append_message(
            layout,
            session_id=session_id,
            transport_id=transport_id,
            role="assistant",
            content=reply,
            metadata={"turn_index": turn_index, "fallback": "provider_failure"},
        )
        return reply

    def _provider_runtime_log(self, message: str) -> None:
        write_runtime_log(self.settings, message, stream=sys.__stdout__)


def _should_retrieve(message: str) -> bool:
    normalized = message.lower()
    markers = [
        "вспомни",
        "помнишь",
        "раньше",
        "что было",
        "remember",
        "recall",
        "earlier",
        "previously",
    ]
    return any(marker in normalized for marker in markers)


def _event_metadata(
    event: dict[str, object],
    event_type: str,
) -> dict[str, object]:
    metadata: dict[str, object] = {"event_type": event_type}
    for key in (
        "reply_target",
        "callback_query_id",
        "sender_id",
        "sender_name",
        "message_id",
    ):
        value = event.get(key)
        if isinstance(value, (str, int, float, bool)):
            metadata[key] = value
        elif isinstance(value, dict):
            metadata[key] = {str(item_key): item_value for item_key, item_value in value.items()}
    return metadata


def _runtime_identity_prompt() -> str:
    return "\n".join(
        [
            "You are Nagient, a modular agent runtime assistant.",
            "Your job is to act through the runtime, not like a passive chatbot.",
            "You can use configured tools to read and write workspace files, run shell "
            "commands, inspect git state, use durable memory, route outbound messages through "
            "configured transports, and schedule future jobs or self-wake tasks.",
            "You have conversation memory with recent context, focused context, retrieval, and "
            "durable notes.",
            "If a user asks what you can do, describe your real runtime capabilities.",
            "If a user asks you to perform an action, prefer tool use over saying you cannot.",
            "Prefer the dedicated workspace.git tools for git operations when possible so the "
            "configured git identity and credentials are applied consistently.",
            "Only say that an action is blocked when a tool, policy, missing configuration, or "
            "provider limitation actually prevents it.",
            "Any shell command must be finite and bounded. Prefer forms like `ping -c 4` or "
            "`curl --max-time 10`, and avoid interactive or continuous commands.",
            "When useful, explain briefly what you are doing before or after tool use.",
        ]
    )


def _provider_failure_reply(
    *,
    error: Exception,
    last_message: str | None,
    previous_results: list[dict[str, object]],
) -> str:
    parts: list[str] = []
    if last_message:
        parts.append(last_message)

    if previous_results:
        parts.append(
            "The tool step finished, but the provider timed out before it could "
            "compose the final reply."
            if _is_timeout_error(error)
            else "The tool step finished, but the provider failed before it could "
            "compose the final reply."
        )
        summary = _summarize_latest_tool_result(previous_results[-1])
        if summary:
            parts.append(summary)
    else:
        parts.append(_friendly_provider_error_message(error))

    if not parts:
        parts.append(_friendly_provider_error_message(error))
    return "\n\n".join(part for part in parts if part).strip()


def _friendly_provider_error_message(error: Exception) -> str:
    message = str(error).strip() or error.__class__.__name__
    if _is_timeout_error(error):
        return (
            "Provider request timed out before the runtime could finish this turn. "
            "This is the model/provider timeout, not a tool timeout. "
            "Retry the request or increase the provider timeout."
        )
    return f"Provider request failed during this turn: {message}"


def _should_defer_assistant_message(assistant_response: AssistantResponse) -> bool:
    if not assistant_response.tool_calls:
        return False
    if assistant_response.message_mode == "after_tools":
        return True
    return _has_tool_placeholders(assistant_response.message)


def _render_deferred_assistant_message(
    *,
    assistant_response: AssistantResponse,
    tool_results: list[ToolExecutionResult],
) -> str | None:
    if not _should_defer_assistant_message(assistant_response):
        return None
    message = assistant_response.message.strip()
    if not message:
        return None
    if not _has_tool_placeholders(message):
        return message
    call_results = {
        call.call_id: tool_results[index].to_dict()
        for index, call in enumerate(assistant_response.tool_calls)
        if index < len(tool_results)
    }
    rendered_message = message
    for match in _TOOL_PLACEHOLDER_RE.finditer(message):
        call_id = match.group("call_id")
        path = match.group("path")
        value = _lookup_tool_placeholder_value(call_results.get(call_id), path)
        if value is None:
            return None
        replacement = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        rendered_message = rendered_message.replace(match.group(0), replacement)
    return rendered_message.strip()


def _has_tool_placeholders(message: str) -> bool:
    return bool(_TOOL_PLACEHOLDER_RE.search(message))


def _lookup_tool_placeholder_value(
    payload: dict[str, object] | None,
    path: str,
) -> object | None:
    if payload is None:
        return None
    current: object = payload
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current


def _summarize_latest_tool_result(result: dict[str, object]) -> str:
    function_name = str(result.get("function_name", "tool"))
    status = str(result.get("status", "unknown"))
    output = result.get("output")
    issues = result.get("issues")
    lines = [f"Latest tool result: {function_name} ({status})."]
    if isinstance(output, dict):
        blocked = output.get("blocked")
        blocked_reason = output.get("blocked_reason")
        command = output.get("effective_command") or output.get("command")
        if isinstance(command, str) and command.strip():
            lines.append(f"Command: {command}")
        if blocked and isinstance(blocked_reason, str) and blocked_reason.strip():
            lines.append(f"Blocked: {blocked_reason.strip()}")
        timed_out = output.get("timed_out")
        timeout_seconds = output.get("timeout_seconds")
        if timed_out:
            lines.append(
                f"Timed out after {timeout_seconds} seconds."
                if isinstance(timeout_seconds, int)
                else "Timed out before the command completed."
            )
        exit_code = output.get("exit_code")
        if isinstance(exit_code, int):
            lines.append(f"Exit code: {exit_code}")
        stdout = output.get("stdout")
        if isinstance(stdout, str) and stdout.strip():
            lines.append(f"stdout:\n{_compact_text(stdout, limit=600)}")
        stderr = output.get("stderr")
        if isinstance(stderr, str) and stderr.strip():
            lines.append(f"stderr:\n{_compact_text(stderr, limit=400)}")
    if isinstance(issues, list):
        issue_messages = [
            str(item.get("message", "")).strip()
            for item in issues
            if isinstance(item, dict) and str(item.get("message", "")).strip()
        ]
        if issue_messages:
            lines.append(f"Issues: {'; '.join(issue_messages[:2])}")
    return "\n".join(lines).strip()


def _compact_text(value: str, *, limit: int) -> str:
    stripped = value.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[:limit].rstrip() + "\n...[truncated]"


def _is_timeout_error(error: Exception) -> bool:
    message = str(error).lower()
    return "timed out" in message or "timeout" in message
