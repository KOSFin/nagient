from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from nagient.app.configuration import read_raw_config, write_raw_config
from nagient.application.services.scheduler_service import SchedulerService, run_at_after
from nagient.application.services.session_memory_service import SessionMemoryService
from nagient.application.services.transport_router_service import TransportRouterService
from nagient.domain.entities.tooling import ToolFunctionManifest, ToolPluginManifest
from nagient.tools.base import BaseToolPlugin, ToolExecutionContext, ToolRiskDecision
from nagient.version import __version__


def _transport_payload_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "transport_id": {"type": "string"},
            "payload": {"type": "object"},
        },
        "required": ["transport_id", "payload"],
        "additionalProperties": False,
    }


class TransportRouterToolPlugin(BaseToolPlugin):
    manifest = ToolPluginManifest(
        plugin_id="transport.router",
        display_name="Transport Router",
        version=__version__,
        namespace="transport.router",
        entrypoint="<builtin>",
        capabilities=["transport", "outbound"],
        functions=[
            ToolFunctionManifest(
                function_name="transport.router.list",
                binding="list_transports",
                description="List configured transport instances and their exposed functions.",
                input_schema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "transports": {
                            "type": "array",
                            "items": {"type": "object"},
                        }
                    },
                    "required": ["transports"],
                },
                permissions=["transport.read"],
            ),
            ToolFunctionManifest(
                function_name="transport.router.send_message",
                binding="send_message",
                description="Send a message through a selected configured transport.",
                input_schema=_transport_payload_schema(),
                output_schema={"type": "object"},
                permissions=["transport.send"],
                side_effect="system",
                auto_approve_when_expected=True,
            ),
            ToolFunctionManifest(
                function_name="transport.router.send_notification",
                binding="send_notification",
                description="Send a transport-level notification through a selected transport.",
                input_schema=_transport_payload_schema(),
                output_schema={"type": "object"},
                permissions=["transport.send"],
                side_effect="system",
                auto_approve_when_expected=True,
            ),
            ToolFunctionManifest(
                function_name="transport.router.send_typing",
                binding="send_typing",
                description="Send a typing indicator or equivalent transport activity signal.",
                input_schema=_transport_payload_schema(),
                output_schema={"type": "object"},
                permissions=["transport.send"],
                side_effect="system",
                auto_approve_when_expected=True,
            ),
            ToolFunctionManifest(
                function_name="transport.router.invoke_custom",
                binding="invoke_custom",
                description="Invoke a custom namespaced transport function explicitly.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "transport_id": {"type": "string"},
                        "function_name": {"type": "string"},
                        "payload": {"type": "object"},
                    },
                    "required": ["transport_id", "function_name", "payload"],
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                permissions=["transport.send"],
                side_effect="system",
            ),
        ],
    )

    def assess_risk(
        self,
        function_name: str,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> ToolRiskDecision:
        del function_name, arguments, context
        return ToolRiskDecision(approval_policy="inherit", checkpoint_required=False)

    def list_transports(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        del arguments
        router = _require_router(context)
        return {"transports": router.list_transports()}

    def send_message(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        transport_id = _require_string(arguments, "transport_id")
        payload = _require_mapping(arguments, "payload")
        router = _require_router(context)
        return router.send_message(transport_id=transport_id, payload=payload)

    def send_notification(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        transport_id = _require_string(arguments, "transport_id")
        payload = _require_mapping(arguments, "payload")
        router = _require_router(context)
        return router.send_notification(transport_id=transport_id, payload=payload)

    def send_typing(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        transport_id = _require_string(arguments, "transport_id")
        payload = _require_mapping(arguments, "payload")
        router = _require_router(context)
        return router.send_typing(transport_id=transport_id, payload=payload)

    def invoke_custom(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        transport_id = _require_string(arguments, "transport_id")
        function_name = _require_string(arguments, "function_name")
        payload = _require_mapping(arguments, "payload")
        router = _require_router(context)
        return router.invoke_custom(
            transport_id=transport_id,
            function_name=function_name,
            payload=payload,
        )


class AgentMemoryToolPlugin(BaseToolPlugin):
    manifest = ToolPluginManifest(
        plugin_id="agent.memory",
        display_name="Agent Memory",
        version=__version__,
        namespace="agent.memory",
        entrypoint="<builtin>",
        capabilities=["memory", "notes"],
        functions=[
            ToolFunctionManifest(
                function_name="agent.memory.search_messages",
                binding="search_messages",
                description="Search stored transcript messages by text.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "session_id": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                permissions=["memory.read"],
            ),
            ToolFunctionManifest(
                function_name="agent.memory.create_note",
                binding="create_note",
                description="Create a durable markdown note for the agent.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "path_hint": {"type": "string"},
                    },
                    "required": ["title", "content"],
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                permissions=["memory.write"],
                side_effect="write",
            ),
            ToolFunctionManifest(
                function_name="agent.memory.update_note",
                binding="update_note",
                description="Update an existing markdown note in the notes directory.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "note_path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["note_path", "content"],
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                permissions=["memory.write"],
                side_effect="write",
            ),
            ToolFunctionManifest(
                function_name="agent.memory.list_notes",
                binding="list_notes",
                description="List agent notes stored in the workspace notes directory.",
                input_schema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                permissions=["memory.read"],
            ),
            ToolFunctionManifest(
                function_name="agent.memory.search_notes",
                binding="search_notes",
                description="Search indexed agent notes by text.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                permissions=["memory.read"],
            ),
        ],
    )

    def search_messages(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        service = _require_memory_service(context)
        query = _require_string(arguments, "query")
        session_id = str(arguments.get("session_id", context.session_id or "")).strip() or None
        limit = _optional_int(arguments, "limit", default=8)
        results = service.search_messages(
            context.workspace,
            query=query,
            session_id=session_id,
            limit=limit,
        )
        return {"results": [item.to_dict() for item in results]}

    def create_note(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        service = _require_memory_service(context)
        title = _require_string(arguments, "title")
        content = _require_string(arguments, "content")
        path_hint = arguments.get("path_hint")
        created_path = service.create_note(
            context.workspace,
            title=title,
            content=content,
            path_hint=str(path_hint) if isinstance(path_hint, str) else None,
        )
        return {"path": str(created_path.relative_to(context.workspace.root))}

    def update_note(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        service = _require_memory_service(context)
        note_path = _require_string(arguments, "note_path")
        content = _require_string(arguments, "content")
        updated_path = service.update_note(
            context.workspace,
            note_path=note_path,
            content=content,
        )
        return {"path": str(updated_path.relative_to(context.workspace.root))}

    def list_notes(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        del arguments
        service = _require_memory_service(context)
        return {"notes": service.list_notes(context.workspace)}

    def search_notes(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        service = _require_memory_service(context)
        query = _require_string(arguments, "query")
        limit = _optional_int(arguments, "limit", default=8)
        return {
            "results": service.search_notes(
                context.workspace,
                query=query,
                limit=limit,
            )
        }


class SystemJobsToolPlugin(BaseToolPlugin):
    manifest = ToolPluginManifest(
        plugin_id="system.jobs",
        display_name="System Jobs",
        version=__version__,
        namespace="system.jobs",
        entrypoint="<builtin>",
        capabilities=["scheduler", "jobs"],
        functions=[
            ToolFunctionManifest(
                function_name="system.jobs.schedule_once",
                binding="schedule_once",
                description="Schedule a one-off self-wake message for the agent runtime.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "run_at": {"type": "string"},
                        "delay_seconds": {"type": "integer", "minimum": 1},
                        "message": {"type": "string"},
                        "name": {"type": "string"},
                        "notes": {"type": "string"},
                        "session_id": {"type": "string"},
                        "transport_id": {"type": "string"},
                    },
                    "required": ["message"],
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                permissions=["jobs.write"],
                side_effect="system",
                auto_approve_when_expected=True,
            ),
            ToolFunctionManifest(
                function_name="system.jobs.schedule_message",
                binding="schedule_message",
                description=(
                    "Schedule a direct outbound message without waking the model again."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "run_at": {"type": "string"},
                        "delay_seconds": {"type": "integer", "minimum": 1},
                        "text": {"type": "string"},
                        "name": {"type": "string"},
                        "notes": {"type": "string"},
                        "session_id": {"type": "string"},
                        "transport_id": {"type": "string"},
                        "reply_target": {"type": "object"},
                    },
                    "required": ["text"],
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                permissions=["jobs.write", "transport.send"],
                side_effect="system",
                approval_policy="required",
                auto_approve_when_expected=True,
            ),
            ToolFunctionManifest(
                function_name="system.jobs.schedule_tool",
                binding="schedule_tool",
                description=(
                    "Schedule an exact tool invocation without waking the model again."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "run_at": {"type": "string"},
                        "delay_seconds": {"type": "integer", "minimum": 1},
                        "tool_id": {"type": "string"},
                        "function_name": {"type": "string"},
                        "arguments": {"type": "object"},
                        "dry_run": {"type": "boolean"},
                        "name": {"type": "string"},
                        "notes": {"type": "string"},
                        "session_id": {"type": "string"},
                        "transport_id": {"type": "string"},
                        "reply_target": {"type": "object"},
                        "success_message": {"type": "string"},
                        "error_message": {"type": "string"},
                    },
                    "required": ["function_name"],
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                permissions=["jobs.write", "tool.invoke"],
                side_effect="system",
                approval_policy="required",
                auto_approve_when_expected=True,
            ),
            ToolFunctionManifest(
                function_name="system.jobs.schedule_interval",
                binding="schedule_interval",
                description="Schedule a recurring self-wake message for the agent runtime.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "interval_seconds": {"type": "integer", "minimum": 1},
                        "message": {"type": "string"},
                        "name": {"type": "string"},
                        "notes": {"type": "string"},
                        "session_id": {"type": "string"},
                        "transport_id": {"type": "string"},
                    },
                    "required": ["interval_seconds", "message"],
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                permissions=["jobs.write"],
                side_effect="system",
                auto_approve_when_expected=True,
            ),
            ToolFunctionManifest(
                function_name="system.jobs.list",
                binding="list_jobs",
                description="List stored scheduler jobs for the current workspace.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "include_history": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                permissions=["jobs.read"],
            ),
            ToolFunctionManifest(
                function_name="system.jobs.cancel",
                binding="cancel_job",
                description="Cancel a scheduled job by id.",
                input_schema={
                    "type": "object",
                    "properties": {"job_id": {"type": "string"}},
                    "required": ["job_id"],
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                permissions=["jobs.write"],
                side_effect="system",
            ),
        ],
    )

    def schedule_once(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        scheduler = _require_scheduler_service(context)
        run_at = _run_at_argument(arguments)
        message = _require_string(arguments, "message")
        name = str(arguments.get("name", "scheduled wake")).strip() or "scheduled wake"
        job = scheduler.schedule_once(
            context.workspace,
            run_at=run_at,
            payload=_wake_payload(arguments, context, message),
            name=name,
            notes=str(arguments.get("notes")) if "notes" in arguments else None,
        )
        return job.to_dict()

    def schedule_message(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        scheduler = _require_scheduler_service(context)
        run_at = _run_at_argument(arguments)
        text = _require_string(arguments, "text")
        name = str(arguments.get("name", "scheduled message")).strip() or "scheduled message"
        job = scheduler.schedule_once(
            context.workspace,
            run_at=run_at,
            payload=_scheduled_message_payload(arguments, context, text),
            name=name,
            notes=str(arguments.get("notes")) if "notes" in arguments else None,
        )
        return job.to_dict()

    def schedule_tool(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        scheduler = _require_scheduler_service(context)
        run_at = _run_at_argument(arguments)
        function_name = _require_string(arguments, "function_name")
        tool_id = str(arguments.get("tool_id", "")).strip()
        tool_arguments = arguments.get("arguments", {})
        if not isinstance(tool_arguments, dict):
            raise ValueError("system.jobs.schedule_tool arguments must be an object.")
        name = str(arguments.get("name", f"scheduled {function_name}")).strip()
        if not name:
            name = f"scheduled {function_name}"
        job = scheduler.schedule_once(
            context.workspace,
            run_at=run_at,
            payload=_scheduled_tool_payload(
                arguments,
                context,
                tool_id=tool_id,
                function_name=function_name,
                tool_arguments={str(key): value for key, value in tool_arguments.items()},
            ),
            name=name,
            notes=str(arguments.get("notes")) if "notes" in arguments else None,
        )
        return job.to_dict()

    def schedule_interval(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        scheduler = _require_scheduler_service(context)
        message = _require_string(arguments, "message")
        interval_seconds = arguments.get("interval_seconds")
        if not isinstance(interval_seconds, int) or interval_seconds <= 0:
            raise ValueError("interval_seconds must be a positive integer.")
        name = str(arguments.get("name", "interval wake")).strip() or "interval wake"
        job = scheduler.schedule_interval(
            context.workspace,
            interval_seconds=interval_seconds,
            payload=_wake_payload(arguments, context, message),
            name=name,
            notes=str(arguments.get("notes")) if "notes" in arguments else None,
        )
        return job.to_dict()

    def list_jobs(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        scheduler = _require_scheduler_service(context)
        jobs = scheduler.list_jobs(context.workspace)
        include_history = bool(arguments.get("include_history", False))
        visible_jobs = [
            job
            for job in jobs
            if include_history or job.status in {"pending", "scheduled", "failed"}
        ]
        return {
            "jobs": [_job_summary(job) for job in visible_jobs],
            "count": len(visible_jobs),
            "active_count": sum(
                1 for job in jobs if job.status in {"pending", "scheduled"}
            ),
            "history_included": include_history,
        }

    def cancel_job(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        scheduler = _require_scheduler_service(context)
        job_id = _require_string(arguments, "job_id")
        return scheduler.cancel_job(context.workspace, job_id).to_dict()


def _wake_payload(
    arguments: Mapping[str, object],
    context: ToolExecutionContext,
    message: str,
) -> dict[str, object]:
    session_id = str(arguments.get("session_id", context.session_id or "system")).strip()
    transport_id = str(
        arguments.get("transport_id", context.transport_id or "console")
    ).strip()
    return {
        "action_type": "agent.wake",
        "session_id": session_id,
        "transport_id": transport_id,
        "message": message,
    }


def _scheduled_message_payload(
    arguments: Mapping[str, object],
    context: ToolExecutionContext,
    text: str,
) -> dict[str, object]:
    session_id = str(arguments.get("session_id", context.session_id or "system")).strip()
    transport_id = str(
        arguments.get("transport_id", context.transport_id or "console")
    ).strip()
    payload: dict[str, object] = {
        "action_type": "transport.send_message",
        "session_id": session_id,
        "transport_id": transport_id,
        "text": text,
    }
    reply_target = arguments.get("reply_target")
    if isinstance(reply_target, dict):
        payload["reply_target"] = {str(key): value for key, value in reply_target.items()}
    return payload


def _scheduled_tool_payload(
    arguments: Mapping[str, object],
    context: ToolExecutionContext,
    *,
    tool_id: str,
    function_name: str,
    tool_arguments: dict[str, object],
) -> dict[str, object]:
    session_id = str(arguments.get("session_id", context.session_id or "system")).strip()
    transport_id = str(
        arguments.get("transport_id", context.transport_id or "console")
    ).strip()
    payload: dict[str, object] = {
        "action_type": "tool.invoke",
        "session_id": session_id,
        "transport_id": transport_id,
        "tool_request": {
            "tool_id": tool_id,
            "function_name": function_name,
            "arguments": tool_arguments,
            "dry_run": bool(arguments.get("dry_run", False)),
            "session_id": session_id,
            "transport_id": transport_id,
            "auto_approve": True,
        },
    }
    reply_target = arguments.get("reply_target")
    if isinstance(reply_target, dict):
        payload["reply_target"] = {str(key): value for key, value in reply_target.items()}
    for key in ("success_message", "error_message"):
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            payload[key] = value.strip()
    return payload


def _run_at_argument(arguments: Mapping[str, object]) -> str:
    delay_seconds = arguments.get("delay_seconds")
    if isinstance(delay_seconds, bool):
        delay_seconds = None
    if isinstance(delay_seconds, int):
        return run_at_after(delay_seconds)
    if isinstance(delay_seconds, str) and delay_seconds.strip().isdigit():
        return run_at_after(int(delay_seconds.strip()))
    return _require_string(arguments, "run_at")


def _job_summary(job: object) -> dict[str, object]:
    run_at = getattr(job, "run_at", None)
    summary: dict[str, object] = {
        "job_id": getattr(job, "job_id", ""),
        "name": getattr(job, "name", ""),
        "status": getattr(job, "status", ""),
        "trigger": getattr(job, "trigger", ""),
    }
    if isinstance(run_at, str) and run_at:
        summary["run_at"] = run_at
        due_in = _seconds_until(run_at)
        if due_in is not None:
            summary["due_in_seconds"] = due_in
    interval_seconds = getattr(job, "interval_seconds", None)
    if isinstance(interval_seconds, int):
        summary["interval_seconds"] = interval_seconds
    last_run_at = getattr(job, "last_run_at", None)
    if isinstance(last_run_at, str) and last_run_at:
        summary["last_run_at"] = last_run_at
    return summary


def _seconds_until(value: str) -> int | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return max(0, int((parsed.astimezone(UTC) - datetime.now(tz=UTC)).total_seconds()))


def _require_string(arguments: Mapping[str, object], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Argument {key!r} must be a non-empty string.")
    return value.strip()


def _require_mapping(arguments: Mapping[str, object], key: str) -> dict[str, object]:
    value = arguments.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Argument {key!r} must be an object.")
    return {str(item_key): item_value for item_key, item_value in value.items()}


class SystemConfigToolPlugin(BaseToolPlugin):
    manifest = ToolPluginManifest(
        plugin_id="system.config",
        display_name="System Config",
        version=__version__,
        namespace="system.config",
        entrypoint="<builtin>",
        capabilities=["config"],
        functions=[
            ToolFunctionManifest(
                function_name="system.config.read",
                binding="read_config",
                description="Read the runtime config file as structured TOML data.",
                input_schema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                permissions=["config.read"],
            ),
            ToolFunctionManifest(
                function_name="system.config.patch",
                binding="patch_config",
                description="Patch one runtime config path after approval.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "value": {},
                    },
                    "required": ["path", "value"],
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                permissions=["config.write"],
                side_effect="system",
                approval_policy="required",
                dry_run_supported=True,
                auto_approve_when_expected=True,
            ),
        ],
    )

    def read_config(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        del arguments
        return {
            "config_file": str(context.settings.config_file),
            "config": read_raw_config(context.settings.config_file),
        }

    def patch_config(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        dotted_path = _require_string(arguments, "path")
        value = arguments.get("value")
        if context.dry_run:
            return {
                "config_file": str(context.settings.config_file),
                "path": dotted_path,
                "value": value,
                "dry_run": True,
            }
        payload = read_raw_config(context.settings.config_file)
        _patch_nested_config_value(payload, dotted_path, value)
        write_raw_config(context.settings.config_file, payload)
        return {
            "config_file": str(context.settings.config_file),
            "path": dotted_path,
            "updated": True,
        }


def _patch_nested_config_value(
    payload: dict[str, object],
    dotted_path: str,
    value: object,
) -> None:
    parts = [part.strip() for part in dotted_path.split(".") if part.strip()]
    if not parts:
        raise ValueError("system.config.patch path must not be empty.")
    current = payload
    for part in parts[:-1]:
        nested = current.get(part)
        if not isinstance(nested, dict):
            nested = {}
            current[part] = nested
        current = nested
    current[parts[-1]] = value


def _optional_int(arguments: Mapping[str, object], key: str, *, default: int) -> int:
    value = arguments.get(key, default)
    if isinstance(value, bool):
        return default
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else default
    return default


def _require_router(context: ToolExecutionContext) -> TransportRouterService:
    service = context.transport_router
    if not isinstance(service, TransportRouterService):
        raise ValueError("Tool execution context is missing transport_router.")
    return service


def _require_memory_service(context: ToolExecutionContext) -> SessionMemoryService:
    service = context.memory_service
    if not isinstance(service, SessionMemoryService):
        raise ValueError("Tool execution context is missing memory_service.")
    return service


def _require_scheduler_service(context: ToolExecutionContext) -> SchedulerService:
    service = context.scheduler_service
    if not isinstance(service, SchedulerService):
        raise ValueError("Tool execution context is missing scheduler_service.")
    return service
