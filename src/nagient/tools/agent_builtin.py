from __future__ import annotations

from collections.abc import Mapping

from nagient.application.services.scheduler_service import SchedulerService
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
            ),
            ToolFunctionManifest(
                function_name="transport.router.send_notification",
                binding="send_notification",
                description="Send a transport-level notification through a selected transport.",
                input_schema=_transport_payload_schema(),
                output_schema={"type": "object"},
                permissions=["transport.send"],
                side_effect="system",
            ),
            ToolFunctionManifest(
                function_name="transport.router.send_typing",
                binding="send_typing",
                description="Send a typing indicator or equivalent transport activity signal.",
                input_schema=_transport_payload_schema(),
                output_schema={"type": "object"},
                permissions=["transport.send"],
                side_effect="system",
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
                        "message": {"type": "string"},
                        "name": {"type": "string"},
                        "notes": {"type": "string"},
                        "session_id": {"type": "string"},
                        "transport_id": {"type": "string"},
                    },
                    "required": ["run_at", "message"],
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                permissions=["jobs.write"],
                side_effect="system",
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
            ),
            ToolFunctionManifest(
                function_name="system.jobs.list",
                binding="list_jobs",
                description="List stored scheduler jobs for the current workspace.",
                input_schema={
                    "type": "object",
                    "properties": {},
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
        run_at = _require_string(arguments, "run_at")
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
        del arguments
        scheduler = _require_scheduler_service(context)
        jobs = scheduler.list_jobs(context.workspace)
        return {"jobs": [job.to_dict() for job in jobs]}

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
