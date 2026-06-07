from __future__ import annotations

import json
import re
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
from nagient.domain.entities.tooling import ToolExecutionRequest, ToolExecutionResult
from nagient.infrastructure.logging import RuntimeLogger, append_runtime_log
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

        approval_reply = self._maybe_resolve_transport_approval(
            layout=layout,
            session_id=session_id,
            transport_id=transport_id,
            event=event,
            text=text,
            provider_id=provider_id,
            runtime_config=runtime_config,
            system_prompt_override=system_prompt_override,
        )
        if approval_reply is not None:
            return approval_reply

        self.logger.info(
            "agent_runtime.inbound_message",
            "Handling inbound message.",
            session_id=session_id,
            transport_id=transport_id,
            event_type=event_type,
            text_preview=_compact_text(text, limit=240),
        )
        append_runtime_log(
            self.settings,
            (
                f"Handling {event_type} from {transport_id} "
                f"(session_id={session_id}): {_compact_text(text, limit=160)}"
            ),
            component="agent.runtime",
        )
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
            self._log_assistant_response(
                session_id=session_id,
                transport_id=transport_id,
                step=turn_index,
                assistant_response=assistant_response,
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
                    self._maybe_send_progress_message(
                        runtime_config=runtime_config,
                        transport_id=transport_id,
                        event=event,
                        message=last_message,
                        assistant_response=assistant_response,
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
                self._log_tool_results(
                    session_id=session_id,
                    transport_id=transport_id,
                    step=turn_index,
                    tool_results=turn_result.tool_results,
                )
                for result in turn_result.tool_results:
                    self.memory_service.append_message(
                        layout,
                        session_id=session_id,
                        transport_id=transport_id,
                        role="tool",
                        content=json.dumps(result.to_dict(), ensure_ascii=False),
                        metadata={"function_name": result.function_name},
                    )

            approval_required_reply = _render_tool_approval_required_reply(
                turn_result.tool_results
            )
            if approval_required_reply is not None:
                self.memory_service.append_message(
                    layout,
                    session_id=session_id,
                    transport_id=transport_id,
                    role="assistant",
                    content=approval_required_reply,
                    metadata={"turn_index": turn_index, "approval_wait": True},
                )
                self.logger.info(
                    "agent_runtime.waiting_for_approval",
                    "Paused agent turn until the user approves a pending tool action.",
                    session_id=session_id,
                    transport_id=transport_id,
                    approvals=[
                        result.approval_request_id
                        for result in turn_result.tool_results
                        if result.approval_request_id
                    ],
                )
                append_runtime_log(
                    self.settings,
                    (
                        "Waiting for approval: "
                        + ", ".join(
                            result.approval_request_id or result.function_name
                            for result in turn_result.tool_results
                            if result.status == "approval_required"
                        )
                    ),
                    component="agent.runtime",
                )
                if self._maybe_send_transport_approval_prompt(
                    transport_id=transport_id,
                    event=event,
                    reply=approval_required_reply,
                    tool_results=turn_result.tool_results,
                ):
                    return None
                return approval_required_reply

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

    def _maybe_resolve_transport_approval(
        self,
        *,
        layout: object,
        session_id: str,
        transport_id: str,
        event: dict[str, object],
        text: str,
        provider_id: str | None,
        runtime_config: RuntimeConfiguration,
        system_prompt_override: str | None,
    ) -> str | None:
        decision = _approval_decision_from_text(text)
        if decision is None:
            return None
        requested_approval_id = _approval_request_id_from_text(text)
        workflow_service = getattr(self.agent_turn_service, "workflow_service", None)
        if workflow_service is None:
            return None
        pending = [
            approval
            for approval in workflow_service.list_approvals()
            if approval.status == "pending"
            and (
                approval.session_id == session_id
                or approval.transport_id == transport_id
            )
        ]
        if not pending:
            return None
        approval = (
            next(
                (
                    item
                    for item in pending
                    if requested_approval_id is not None
                    and item.request_id == requested_approval_id
                ),
                None,
            )
            or pending[-1]
        )
        self.memory_service.append_message(
            layout,
            session_id=session_id,
            transport_id=transport_id,
            role="user",
            content=text,
            metadata={"approval_decision": decision, "approval_request_id": approval.request_id},
        )
        result = workflow_service.resolve_approval(approval.request_id, decision)
        self.logger.info(
            "agent_runtime.approval_resolved",
            "Resolved pending approval from transport message.",
            session_id=session_id,
            transport_id=transport_id,
            approval_request_id=approval.request_id,
            decision=decision,
            status=result.status,
        )
        append_runtime_log(
            self.settings,
            (
                f"Resolved approval {approval.request_id} from {transport_id} "
                f"with decision={decision}, status={result.status}."
            ),
            component="agent.runtime",
        )
        reply = _render_approval_result_reply(result.to_dict())
        should_resume = _approval_should_resume_model(
            approval.metadata,
            status=result.status,
        )
        message_override = _approval_message_override(
            approval.metadata,
            status=result.status,
        )
        if message_override:
            reply = message_override
        elif decision == "approve" and should_resume:
            resumed = self._try_provider_resume_after_approval(
                layout=layout,
                session_id=session_id,
                transport_id=transport_id,
                provider_id=provider_id,
                runtime_config=runtime_config,
                system_prompt_override=system_prompt_override,
                approval_result=result.to_dict(),
            )
            if resumed is not None:
                reply = resumed
        self.memory_service.append_message(
            layout,
            session_id=session_id,
            transport_id=transport_id,
            role="assistant",
            content=reply,
            metadata={
                "approval_result": result.status,
                "approval_request_id": approval.request_id,
            },
        )
        if (
            requested_approval_id is not None
            and self._maybe_finish_transport_approval_callback(
                transport_id=transport_id,
                event=event,
                reply=reply,
                decision=decision,
            )
        ):
            return None
        return reply

    def _maybe_send_transport_approval_prompt(
        self,
        *,
        transport_id: str,
        event: dict[str, object],
        reply: str,
        tool_results: list[ToolExecutionResult],
    ) -> bool:
        if self.transport_router is None or transport_id != "telegram":
            return False
        reply_target = event.get("reply_target")
        if not isinstance(reply_target, dict) or not reply_target:
            return False
        approval_id = _latest_approval_request_id(tool_results)
        if approval_id is None:
            return False
        payload = {str(key): value for key, value in reply_target.items()}
        payload["text"] = reply
        payload["reply_markup"] = _telegram_approval_reply_markup(approval_id)
        try:
            self.transport_router.send_message(
                transport_id=transport_id,
                payload=payload,
            )
        except Exception as exc:
            self.logger.warning(
                "agent_runtime.approval_prompt_failed",
                "Failed to send transport approval prompt.",
                transport_id=transport_id,
                approval_request_id=approval_id,
                error=str(exc),
            )
            return False
        append_runtime_log(
            self.settings,
            f"Sent approval prompt through {transport_id} for {approval_id}.",
            component="agent.runtime",
        )
        return True

    def _maybe_finish_transport_approval_callback(
        self,
        *,
        transport_id: str,
        event: dict[str, object],
        reply: str,
        decision: str,
    ) -> bool:
        if self.transport_router is None or transport_id != "telegram":
            return False
        callback_id = str(event.get("callback_query_id", "")).strip()
        reply_target = event.get("reply_target")
        if not callback_id and not isinstance(reply_target, dict):
            return False
        handled = False
        if callback_id:
            try:
                self.transport_router.invoke_custom(
                    transport_id=transport_id,
                    function_name="telegram.answerCallback",
                    payload={
                        "callback_id": callback_id,
                        "text": "Approved" if decision == "approve" else "Cancelled",
                    },
                )
                handled = True
            except Exception as exc:
                self.logger.debug(
                    "agent_runtime.approval_callback_answer_failed",
                    "Failed to answer approval callback.",
                    transport_id=transport_id,
                    error=str(exc),
                )
        message_id = str(event.get("message_id", "")).strip()
        if isinstance(reply_target, dict) and message_id:
            payload = {str(key): value for key, value in reply_target.items()}
            payload.update(
                {
                    "message_id": message_id,
                    "text": reply,
                    "reply_markup": {"inline_keyboard": []},
                }
            )
            try:
                self.transport_router.invoke_custom(
                    transport_id=transport_id,
                    function_name="telegram.editMessage",
                    payload=payload,
                )
                handled = True
            except Exception as exc:
                self.logger.debug(
                    "agent_runtime.approval_callback_edit_failed",
                    "Failed to edit approval callback message.",
                    transport_id=transport_id,
                    error=str(exc),
                )
        return handled

    def _try_provider_resume_after_approval(
        self,
        *,
        layout: object,
        session_id: str,
        transport_id: str,
        provider_id: str | None,
        runtime_config: RuntimeConfiguration,
        system_prompt_override: str | None,
        approval_result: dict[str, object],
    ) -> str | None:
        prompt_context = self.memory_service.build_prompt_context(
            layout,
            session_id=session_id,
            config=runtime_config.agent.memory,
            retrieval_query=None,
        )
        try:
            assistant_response = self.provider_service.generate_assistant_response(
                message=(
                    "The user approved the pending action. Summarize the completed "
                    "result clearly and do not request approval again unless another "
                    "new action is required."
                ),
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
                previous_results=[
                    {
                        "function_name": "workflow.approval.resolve",
                        "status": approval_result.get("status"),
                        "output": approval_result.get("resume_payload", {}),
                    }
                ],
                runtime_log=self._provider_runtime_log,
            )
        except Exception as exc:
            self.logger.warning(
                "agent_runtime.approval_resume_failed",
                "Failed to resume provider after approval.",
                session_id=session_id,
                transport_id=transport_id,
                error=str(exc),
            )
            return None
        resumed_message = str(assistant_response.message).strip()
        if not resumed_message:
            return None
        if assistant_response.tool_calls:
            self.logger.warning(
                "agent_runtime.approval_resume_tool_calls_ignored",
                "Provider returned tool calls during approval resume; keeping execution bounded.",
                session_id=session_id,
                transport_id=transport_id,
                tool_calls=[
                    call.request.function_name for call in assistant_response.tool_calls
                ],
            )
        return resumed_message

    def handle_scheduled_job(self, job: JobRecord) -> str | None:
        action_type = str(job.payload.get("action_type", "")).strip()
        if action_type == "transport.send_message":
            return self._handle_scheduled_message(job)
        if action_type == "tool.invoke":
            return self._handle_scheduled_tool(job)
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
        event: dict[str, object] = {
            "event_type": "system_wake",
            "session_id": session_id,
            "text": message,
        }
        reply_target = _scheduled_reply_target(job.payload, transport_id, session_id)
        if reply_target:
            event["reply_target"] = reply_target
        reply = self.handle_inbound_event(
            transport_id,
            event,
        )
        if reply and self._maybe_send_scheduled_reply(
            transport_id=transport_id,
            reply_target=reply_target,
            reply=reply,
            job_id=job.job_id,
        ):
            return None
        return reply

    def _handle_scheduled_message(self, job: JobRecord) -> str | None:
        transport_id = str(job.payload.get("transport_id", "console")).strip() or "console"
        session_id = str(job.payload.get("session_id", "system")).strip() or "system"
        text = str(job.payload.get("text", "")).strip()
        if not text:
            return None
        reply_target = _scheduled_reply_target(job.payload, transport_id, session_id)
        if self._maybe_send_scheduled_reply(
            transport_id=transport_id,
            reply_target=reply_target,
            reply=text,
            job_id=job.job_id,
        ):
            return None
        return text

    def _handle_scheduled_tool(self, job: JobRecord) -> str | None:
        raw_request = job.payload.get("tool_request")
        if not isinstance(raw_request, dict):
            self.logger.warning(
                "agent_runtime.scheduled_tool_invalid",
                "Skipped scheduled tool job without a valid tool_request.",
                job_id=job.job_id,
            )
            return None
        tool_service = getattr(self.agent_turn_service, "tool_service", None)
        if tool_service is None:
            self.logger.warning(
                "agent_runtime.scheduled_tool_unavailable",
                "Skipped scheduled tool job because tool service is unavailable.",
                job_id=job.job_id,
            )
            return None
        transport_id = str(job.payload.get("transport_id", "console")).strip() or "console"
        session_id = str(job.payload.get("session_id", "system")).strip() or "system"
        request_payload = {str(key): value for key, value in raw_request.items()}
        request_payload.setdefault("session_id", session_id)
        request_payload.setdefault("transport_id", transport_id)
        request_payload["auto_approve"] = True
        result = tool_service.invoke(ToolExecutionRequest.from_dict(request_payload))
        result_payload = result.to_dict()
        append_runtime_log(
            self.settings,
            (
                f"Scheduled tool job {job.job_id} executed "
                f"{result.function_name} with status={result.status}."
            ),
            component="agent.runtime",
        )
        reply = _scheduled_tool_message(job.payload, result_payload)
        if not reply:
            return None
        reply_target = _scheduled_reply_target(job.payload, transport_id, session_id)
        if self._maybe_send_scheduled_reply(
            transport_id=transport_id,
            reply_target=reply_target,
            reply=reply,
            job_id=job.job_id,
        ):
            return None
        return reply

    def _maybe_send_scheduled_reply(
        self,
        *,
        transport_id: str,
        reply_target: dict[str, object],
        reply: str,
        job_id: str,
    ) -> bool:
        if self.transport_router is None or transport_id == "console" or not reply_target:
            return False
        payload = dict(reply_target)
        payload["text"] = reply
        try:
            self.transport_router.send_message(
                transport_id=transport_id,
                payload=payload,
            )
        except Exception as exc:
            self.logger.warning(
                "agent_runtime.scheduled_reply_failed",
                "Failed to send scheduled job reply through transport.",
                transport_id=transport_id,
                job_id=job_id,
                error=str(exc),
            )
            return False
        append_runtime_log(
            self.settings,
            f"Sent scheduled job reply through {transport_id} for {job_id}.",
            component="agent.runtime",
        )
        return True

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
                        "input_schema": _tool_input_schema_with_approval_context(
                            function.input_schema,
                            side_effect=function.side_effect,
                            approval_policy=function.approval_policy,
                        ),
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

    def _maybe_send_progress_message(
        self,
        *,
        runtime_config: RuntimeConfiguration,
        transport_id: str,
        event: dict[str, object],
        message: str,
        assistant_response: AssistantResponse,
    ) -> bool:
        if (
            not runtime_config.agent.progress.enabled
            or self.transport_router is None
            or transport_id == "console"
            or not assistant_response.tool_calls
            or _should_defer_assistant_message(assistant_response)
        ):
            return False
        reply_target = event.get("reply_target")
        if not isinstance(reply_target, dict) or not reply_target:
            return False
        payload = {str(key): value for key, value in reply_target.items()}
        payload["text"] = message
        try:
            self.transport_router.send_message(
                transport_id=transport_id,
                payload=payload,
            )
        except Exception as exc:
            self.logger.debug(
                "agent_runtime.progress_message_failed",
                "Could not send progress message through transport.",
                transport_id=transport_id,
                error=str(exc),
            )
            return False
        append_runtime_log(
            self.settings,
            f"Sent progress message through {transport_id}.",
            component="agent.runtime",
        )
        return True

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
        append_runtime_log(self.settings, message, component="provider.runtime")

    def _log_assistant_response(
        self,
        *,
        session_id: str,
        transport_id: str,
        step: int,
        assistant_response: AssistantResponse,
    ) -> None:
        self.logger.info(
            "agent_runtime.assistant_response",
            "Received assistant response from provider.",
            session_id=session_id,
            transport_id=transport_id,
            step=step,
            message_mode=assistant_response.message_mode,
            tool_calls=[
                call.request.function_name for call in assistant_response.tool_calls
            ],
            notifications=len(assistant_response.notifications),
            approvals=len(assistant_response.approval_requests),
            interactions=len(assistant_response.interaction_requests),
            message_preview=_compact_text(assistant_response.message, limit=240)
            if assistant_response.message.strip()
            else "",
        )

    def _log_tool_results(
        self,
        *,
        session_id: str,
        transport_id: str,
        step: int,
        tool_results: list[ToolExecutionResult],
    ) -> None:
        self.logger.info(
            "agent_runtime.tool_results",
            "Completed assistant-requested tool batch.",
            session_id=session_id,
            transport_id=transport_id,
            step=step,
            results=[_tool_result_log_summary(item) for item in tool_results],
        )
        append_runtime_log(
            self.settings,
            (
                f"Tool results for {transport_id}/{session_id}: "
                + "; ".join(
                    f"{item.function_name}={item.status}" for item in tool_results
                )
            ),
            component="agent.runtime",
        )


def _should_retrieve(message: str) -> bool:
    normalized = message.lower()
    markers = [
        "вспомни",
        "помнишь",
        "раньше",
        "что было",
        "о чем",
        "говорили",
        "remember",
        "recall",
        "earlier",
        "previously",
    ]
    return any(marker in normalized for marker in markers)


def _approval_decision_from_text(message: str) -> str | None:
    normalized = message.strip().lower()
    normalized = normalized.strip(" .,!?:;")
    callback_decision = _approval_callback_decision(normalized)
    if callback_decision is not None:
        return callback_decision
    approve_words = {
        "approve",
        "approved",
        "approval",
        "yes",
        "y",
        "ok",
        "okay",
        "да",
        "ок",
        "окей",
        "подтверждаю",
        "разрешаю",
        "апрув",
        "аппрув",
        "опрув",
        "опруф",
    }
    reject_words = {
        "reject",
        "no",
        "n",
        "cancel",
        "stop",
        "нет",
        "отклонить",
        "отмена",
        "отбой",
        "не надо",
        "запретить",
    }
    if normalized in approve_words:
        return "approve"
    if normalized in reject_words:
        return "reject" if normalized not in {"cancel", "отмена", "отбой"} else "cancel"
    return None


def _approval_callback_decision(normalized: str) -> str | None:
    parts = normalized.split(":")
    if len(parts) == 4 and parts[0] == "nagient" and parts[1] == "approval":
        if parts[3] in {"approve", "reject", "cancel"}:
            return parts[3]
    return None


def _approval_request_id_from_text(message: str) -> str | None:
    parts = message.strip().split(":")
    if len(parts) == 4 and parts[0] == "nagient" and parts[1] == "approval":
        request_id = parts[2].strip()
        if request_id:
            return request_id
    return None


def _latest_approval_request_id(
    tool_results: list[ToolExecutionResult],
) -> str | None:
    pending = [
        result.approval_request_id
        for result in tool_results
        if result.status == "approval_required" and result.approval_request_id
    ]
    return pending[-1] if pending else None


def _telegram_approval_reply_markup(approval_id: str) -> dict[str, object]:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Approve",
                    "callback_data": f"nagient:approval:{approval_id}:approve",
                },
                {
                    "text": "Cancel",
                    "callback_data": f"nagient:approval:{approval_id}:cancel",
                },
            ]
        ]
    }


def _render_tool_approval_required_reply(
    tool_results: list[ToolExecutionResult],
) -> str | None:
    pending = [
        result
        for result in tool_results
        if result.status == "approval_required" and result.approval_request_id
    ]
    if not pending:
        return None
    if len(pending) == 1:
        result = pending[0]
        return "\n".join(
            [
                "Нужно подтверждение для действия:",
                f"- `{result.function_name}`",
                "",
                "Напиши `approve` / `опрув`, чтобы выполнить, или `cancel`, чтобы отменить.",
            ]
        )
    lines = ["Нужно подтверждение для нескольких действий:"]
    for result in pending:
        lines.append(f"- `{result.function_name}`")
    lines.extend(
        [
            "",
            "Напиши `approve` / `опрув`, чтобы выполнить последнее ожидающее действие, "
            "или `cancel`, чтобы отменить.",
        ]
    )
    return "\n".join(lines)


def _render_approval_result_reply(payload: dict[str, object]) -> str:
    status = str(payload.get("status", ""))
    decision = str(payload.get("decision", ""))
    logs = payload.get("logs", [])
    if status == "approved":
        lines = ["Подтверждение принято, действие выполнено."]
    elif status == "failed":
        lines = ["Подтверждение принято, но действие упало."]
    elif decision in {"reject", "cancel"}:
        lines = ["Ок, действие отменено."]
    else:
        lines = [f"Approval обработан со статусом `{status or decision}`."]
    if isinstance(logs, list):
        for log in logs[:3]:
            if isinstance(log, str) and log.strip():
                lines.append(f"- {log.strip()}")
    return "\n".join(lines)


def _approval_message_override(
    metadata: dict[str, object],
    *,
    status: str,
) -> str:
    if status == "approved":
        message = metadata.get("on_success_message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    if status == "failed" and metadata.get("on_error") == "message":
        message = metadata.get("on_error_message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return ""


def _approval_should_resume_model(
    metadata: dict[str, object],
    *,
    status: str,
) -> bool:
    if status == "approved":
        return metadata.get("on_success") == "resume_model"
    if status == "failed":
        return metadata.get("on_error", "resume_model") == "resume_model"
    return False


def _tool_input_schema_with_approval_context(
    input_schema: dict[str, object],
    *,
    side_effect: str,
    approval_policy: str,
) -> dict[str, object]:
    if side_effect == "read" and approval_policy == "never":
        return dict(input_schema)
    schema = dict(input_schema)
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        properties = {}
    else:
        properties = dict(properties)
    properties.setdefault(
        "approval_context",
        {
            "type": "object",
            "description": (
                "Optional approval policy hint. Set expected_by_user only when the user "
                "clearly requested this exact side-effecting action."
            ),
            "properties": {
                "expected_by_user": {"type": "boolean"},
                "reason": {"type": "string"},
                "on_success": {
                    "type": "string",
                    "enum": ["message", "resume_model", "none"],
                },
                "on_success_message": {"type": "string"},
                "on_error": {
                    "type": "string",
                    "enum": ["resume_model", "message", "none"],
                },
                "on_error_message": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "additionalProperties": True,
        },
    )
    schema["properties"] = properties
    if schema.get("additionalProperties") is False:
        schema["additionalProperties"] = True
    return schema


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


def _scheduled_reply_target(
    payload: dict[str, object],
    transport_id: str,
    session_id: str,
) -> dict[str, object]:
    reply_target = payload.get("reply_target")
    if isinstance(reply_target, dict):
        return {str(key): value for key, value in reply_target.items()}
    if transport_id == "telegram" and session_id.startswith("telegram:"):
        chat_id = session_id.split(":", 1)[1].strip()
        if chat_id:
            return {"chat_id": chat_id}
    return {}


def _scheduled_tool_message(
    job_payload: dict[str, object],
    result_payload: dict[str, object],
) -> str:
    status = str(result_payload.get("status", ""))
    override_key = "success_message" if status == "success" else "error_message"
    override = job_payload.get(override_key)
    if isinstance(override, str) and override.strip():
        return override.strip()
    return _summarize_single_tool_result(
        result_payload,
        heading="Scheduled tool result",
    )


def _runtime_identity_prompt() -> str:
    return "\n".join(
        [
            "You are Nagient, a modular agent runtime assistant.",
            "Your job is to act through the runtime, not like a passive chatbot.",
            "You can use configured tools to read and write workspace files, run shell "
            "commands, inspect git state, use durable memory, route outbound messages through "
            "configured transports, and schedule future jobs or self-wake tasks.",
            "For short delayed reminders, use system.jobs.schedule_once with delay_seconds "
            "instead of putting phrases like 'in 10 seconds' into run_at.",
            "You have conversation memory with recent context, focused context, retrieval, and "
            "durable notes.",
            "If a user asks what you can do, describe your real runtime capabilities.",
            "If a user asks you to perform an action, prefer tool use over saying you cannot.",
            "Prefer the dedicated workspace.git tools for git operations when possible so the "
            "configured git identity and credentials are applied consistently.",
            "For repository commit/push workflows, use workspace.git.run with git subcommands "
            "instead of GitHub REST requests unless the user specifically asks for a GitHub API "
            "operation.",
            "Use github.api.get_authenticated_user and github.api.list_repositories when the "
            "user asks about the connected GitHub account or repository list.",
            "Use github.api.request for GitHub API endpoints that are not covered by a more "
            "specific GitHub tool function, including repository or project settings updates.",
            "Only say that an action is blocked when a tool, policy, missing configuration, or "
            "provider limitation actually prevents it.",
            "When reporting tool results to the user, summarize them in a compact human form. "
            "Do not paste raw JSON arrays unless the user explicitly asks for raw JSON.",
            "Any shell command must be finite and bounded. Prefer forms like `ping -c 4` or "
            "`curl --max-time 10`, and avoid interactive or continuous commands.",
            "For side-effecting tool calls, you may include `approval_context` in arguments. "
            "Set `expected_by_user=true` only when the user clearly requested that exact action. "
            "Use `on_success_message` for a final user-facing message that can be sent after "
            "approval without another model call; use `on_error='resume_model'` when failures "
            "should be sent back to the model.",
            "For delayed plain messages, use system.jobs.schedule_message so the runtime sends "
            "the prepared text directly without waking the model again.",
            "For delayed exact actions, use system.jobs.schedule_tool so the approval decision "
            "happens when scheduling and the stored tool request runs directly when due.",
            "Use agent.wake jobs only when the future task genuinely needs fresh model reasoning.",
            "Use system.config.read to inspect runtime configuration and system.config.patch "
            "to request approved config edits.",
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
        summary = _summarize_tool_results(previous_results)
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


def _summarize_tool_results(results: list[dict[str, object]]) -> str:
    if not results:
        return ""
    if len(results) == 1:
        return _summarize_single_tool_result(results[0], heading="Latest tool result")

    lines = ["Recent tool results:"]
    for result in results[-4:]:
        lines.extend(_tool_result_summary_lines(result))
    return "\n".join(lines).strip()


def _summarize_single_tool_result(
    result: dict[str, object],
    *,
    heading: str,
) -> str:
    lines = _tool_result_summary_lines(result)
    if not lines:
        return ""
    lines[0] = lines[0].replace("Tool result", heading, 1)
    return "\n".join(lines).strip()


def _tool_result_summary_lines(result: dict[str, object]) -> list[str]:
    function_name = str(result.get("function_name", "tool"))
    status = str(result.get("status", "unknown"))
    output = result.get("output")
    issues = result.get("issues")
    lines = [f"Tool result: {function_name} ({status})."]
    if isinstance(output, dict):
        blocked = output.get("blocked")
        blocked_reason = output.get("blocked_reason")
        command = output.get("effective_command") or output.get("command")
        if isinstance(command, str) and command.strip():
            lines.append(f"Command: {command}")
        output_status = output.get("status")
        if (
            isinstance(output_status, str)
            and output_status.strip()
            and output_status.strip() != status
        ):
            lines.append(f"Output status: {output_status.strip()}")
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
        if isinstance(output.get("results"), list):
            lines.append(f"Results: {len(output['results'])}")
        if isinstance(output.get("notes"), list):
            lines.append(f"Notes: {len(output['notes'])}")
        if isinstance(output.get("transports"), list):
            lines.append(f"Transports: {len(output['transports'])}")
        chat_id = output.get("chat_id")
        if isinstance(chat_id, (str, int)) and str(chat_id).strip():
            lines.append(f"Chat id: {chat_id}")
        message_id = output.get("message_id")
        if isinstance(message_id, (str, int)) and str(message_id).strip():
            lines.append(f"Message id: {message_id}")
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
    return lines


def _tool_result_log_summary(result: ToolExecutionResult) -> dict[str, object]:
    payload: dict[str, object] = {
        "function_name": result.function_name,
        "status": result.status,
    }
    if isinstance(result.output.get("status"), (str, int, float, bool)):
        payload["output_status"] = result.output["status"]
    if isinstance(result.output.get("chat_id"), (str, int)):
        payload["chat_id"] = result.output["chat_id"]
    if isinstance(result.output.get("message_id"), (str, int)):
        payload["message_id"] = result.output["message_id"]
    if isinstance(result.output.get("results"), list):
        payload["results_count"] = len(result.output["results"])
    if isinstance(result.output.get("notes"), list):
        payload["notes_count"] = len(result.output["notes"])
    if isinstance(result.output.get("transports"), list):
        payload["transports_count"] = len(result.output["transports"])
    stdout = result.output.get("stdout")
    if isinstance(stdout, str) and stdout.strip():
        payload["stdout_preview"] = _compact_text(stdout, limit=160)
    stderr = result.output.get("stderr")
    if isinstance(stderr, str) and stderr.strip():
        payload["stderr_preview"] = _compact_text(stderr, limit=160)
    if result.issues:
        payload["issues"] = [issue.message for issue in result.issues[:2]]
    return payload


def _compact_text(value: str, *, limit: int) -> str:
    stripped = value.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[:limit].rstrip() + "\n...[truncated]"


def _is_timeout_error(error: Exception) -> bool:
    message = str(error).lower()
    return "timed out" in message or "timeout" in message
