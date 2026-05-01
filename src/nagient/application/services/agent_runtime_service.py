from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from nagient.app.configuration import RuntimeConfiguration, load_runtime_configuration
from nagient.app.settings import Settings
from nagient.domain.entities.agent_runtime import (
    AgentTurnContext,
    AgentTurnRequest,
    ConfigMutationIntent,
    NotificationIntent,
)
from nagient.domain.entities.jobs import JobRecord
from nagient.infrastructure.logging import RuntimeLogger
from nagient.tools.registry import ToolPluginRegistry
from nagient.workspace.manager import WorkspaceManager


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
            )
            if assistant_response.message.strip():
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
            "Only say that an action is blocked when a tool, policy, missing configuration, or "
            "provider limitation actually prevents it.",
            "When useful, explain briefly what you are doing before or after tool use.",
        ]
    )
