from __future__ import annotations

from dataclasses import dataclass, field

from nagient.domain.entities.security import ApprovalRequest, InteractionRequest
from nagient.domain.entities.tooling import ToolExecutionRequest, ToolExecutionResult


@dataclass(frozen=True)
class NotificationIntent:
    level: str
    message: str
    transport_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "level": self.level,
            "message": self.message,
            "metadata": dict(self.metadata),
        }
        if self.transport_id is not None:
            payload["transport_id"] = self.transport_id
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> NotificationIntent:
        metadata = payload.get("metadata")
        return cls(
            level=str(payload.get("level", "info")),
            message=str(payload.get("message", "")),
            transport_id=str(payload["transport_id"]) if "transport_id" in payload else None,
            metadata=dict(metadata) if isinstance(metadata, dict) else {},
        )


@dataclass(frozen=True)
class ConfigMutationIntent:
    path: str
    value: object
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "value": self.value,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ConfigMutationIntent:
        return cls(
            path=str(payload.get("path", "")),
            value=payload.get("value"),
            reason=str(payload.get("reason", "")),
        )


@dataclass(frozen=True)
class NormalizedToolCall:
    call_id: str
    request: ToolExecutionRequest

    def to_dict(self) -> dict[str, object]:
        return {
            "call_id": self.call_id,
            "request": self.request.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> NormalizedToolCall:
        request = payload.get("request", {})
        return cls(
            call_id=str(payload.get("call_id", "")),
            request=ToolExecutionRequest.from_dict(request)
            if isinstance(request, dict)
            else ToolExecutionRequest("", ""),
        )


@dataclass(frozen=True)
class AssistantResponse:
    message: str
    message_mode: str = "immediate"
    tool_calls: list[NormalizedToolCall] = field(default_factory=list)
    interaction_requests: list[InteractionRequest] = field(default_factory=list)
    approval_requests: list[ApprovalRequest] = field(default_factory=list)
    notifications: list[NotificationIntent] = field(default_factory=list)
    config_mutations: list[ConfigMutationIntent] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "message": self.message,
            "message_mode": self.message_mode,
            "tool_calls": [call.to_dict() for call in self.tool_calls],
            "interaction_requests": [
                request.to_dict() for request in self.interaction_requests
            ],
            "approval_requests": [request.to_dict() for request in self.approval_requests],
            "notifications": [notification.to_dict() for notification in self.notifications],
            "config_mutations": [mutation.to_dict() for mutation in self.config_mutations],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> AssistantResponse:
        tool_calls = payload.get("tool_calls")
        interaction_requests = payload.get("interaction_requests")
        approval_requests = payload.get("approval_requests")
        notifications = payload.get("notifications")
        config_mutations = payload.get("config_mutations")
        return cls(
            message=str(payload.get("message", "")),
            message_mode=_normalize_message_mode(payload.get("message_mode")),
            tool_calls=[
                NormalizedToolCall.from_dict(item)
                for item in tool_calls
                if isinstance(item, dict)
            ]
            if isinstance(tool_calls, list)
            else [],
            interaction_requests=[
                InteractionRequest.from_dict(item)
                for item in interaction_requests
                if isinstance(item, dict)
            ]
            if isinstance(interaction_requests, list)
            else [],
            approval_requests=[
                ApprovalRequest.from_dict(item)
                for item in approval_requests
                if isinstance(item, dict)
            ]
            if isinstance(approval_requests, list)
            else [],
            notifications=[
                NotificationIntent.from_dict(item)
                for item in notifications
                if isinstance(item, dict)
            ]
            if isinstance(notifications, list)
            else [],
            config_mutations=[
                ConfigMutationIntent.from_dict(item)
                for item in config_mutations
                if isinstance(item, dict)
            ]
            if isinstance(config_mutations, list)
            else [],
        )


def _normalize_message_mode(value: object) -> str:
    if not isinstance(value, str):
        return "immediate"
    normalized = value.strip().lower()
    if normalized == "after_tools":
        return "after_tools"
    return "immediate"


@dataclass(frozen=True)
class AgentTurnContext:
    session_id: str
    transport_id: str
    workspace_root: str | None = None
    workspace_mode: str | None = None
    previous_results: list[dict[str, object]] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "session_id": self.session_id,
            "transport_id": self.transport_id,
            "previous_results": list(self.previous_results),
            "metadata": dict(self.metadata),
        }
        if self.workspace_root is not None:
            payload["workspace_root"] = self.workspace_root
        if self.workspace_mode is not None:
            payload["workspace_mode"] = self.workspace_mode
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> AgentTurnContext:
        previous_results = payload.get("previous_results")
        metadata = payload.get("metadata")
        return cls(
            session_id=str(payload.get("session_id", "")),
            transport_id=str(payload.get("transport_id", "console")),
            workspace_root=(
                str(payload["workspace_root"]) if "workspace_root" in payload else None
            ),
            workspace_mode=(
                str(payload["workspace_mode"]) if "workspace_mode" in payload else None
            ),
            previous_results=[
                dict(item) for item in previous_results if isinstance(item, dict)
            ]
            if isinstance(previous_results, list)
            else [],
            metadata=dict(metadata) if isinstance(metadata, dict) else {},
        )


@dataclass(frozen=True)
class AgentTurnRequest:
    request_id: str
    user_message: str
    context: AgentTurnContext
    assistant_response: AssistantResponse

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "user_message": self.user_message,
            "context": self.context.to_dict(),
            "assistant_response": self.assistant_response.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> AgentTurnRequest:
        context = payload.get("context", {})
        assistant_response = payload.get("assistant_response", {})
        return cls(
            request_id=str(payload.get("request_id", "")),
            user_message=str(payload.get("user_message", "")),
            context=AgentTurnContext.from_dict(context)
            if isinstance(context, dict)
            else AgentTurnContext("", "console"),
            assistant_response=AssistantResponse.from_dict(assistant_response)
            if isinstance(assistant_response, dict)
            else AssistantResponse(""),
        )


@dataclass(frozen=True)
class AgentTurnResult:
    request_id: str
    session_id: str
    transport_id: str
    message: str
    tool_results: list[ToolExecutionResult] = field(default_factory=list)
    interaction_requests: list[InteractionRequest] = field(default_factory=list)
    approval_requests: list[ApprovalRequest] = field(default_factory=list)
    notifications: list[NotificationIntent] = field(default_factory=list)
    config_mutations: list[ConfigMutationIntent] = field(default_factory=list)
    checkpoint_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "transport_id": self.transport_id,
            "message": self.message,
            "tool_results": [result.to_dict() for result in self.tool_results],
            "interaction_requests": [
                request.to_dict() for request in self.interaction_requests
            ],
            "approval_requests": [request.to_dict() for request in self.approval_requests],
            "notifications": [notification.to_dict() for notification in self.notifications],
            "config_mutations": [mutation.to_dict() for mutation in self.config_mutations],
        }
        if self.checkpoint_id is not None:
            payload["checkpoint_id"] = self.checkpoint_id
        return payload
