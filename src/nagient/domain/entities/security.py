from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SecretBinding:
    target_kind: str
    target_id: str

    def to_dict(self) -> dict[str, str]:
        return {
            "target_kind": self.target_kind,
            "target_id": self.target_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> SecretBinding:
        return cls(
            target_kind=str(payload.get("target_kind", "")),
            target_id=str(payload.get("target_id", "")),
        )


@dataclass(frozen=True)
class SecretMetadata:
    name: str
    scope: str
    exists: bool
    bindings: list[SecretBinding] = field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "name": self.name,
            "scope": self.scope,
            "exists": self.exists,
            "bindings": [binding.to_dict() for binding in self.bindings],
        }
        if self.created_at is not None:
            payload["created_at"] = self.created_at
        if self.updated_at is not None:
            payload["updated_at"] = self.updated_at
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> SecretMetadata:
        bindings = payload.get("bindings")
        return cls(
            name=str(payload.get("name", "")),
            scope=str(payload.get("scope", "tool")),
            exists=bool(payload.get("exists", False)),
            bindings=[
                SecretBinding.from_dict(item)
                for item in bindings
                if isinstance(item, dict)
            ]
            if isinstance(bindings, list)
            else [],
            created_at=str(payload["created_at"]) if "created_at" in payload else None,
            updated_at=str(payload["updated_at"]) if "updated_at" in payload else None,
        )


@dataclass(frozen=True)
class PostSubmitAction:
    action_type: str
    payload: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "action_type": self.action_type,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> PostSubmitAction:
        action_payload = payload.get("payload")
        return cls(
            action_type=str(payload.get("action_type", "")),
            payload=dict(action_payload) if isinstance(action_payload, dict) else {},
        )


@dataclass(frozen=True)
class InteractionRequest:
    request_id: str
    session_id: str
    transport_id: str
    interaction_type: str
    prompt: str
    status: str
    created_at: str
    post_submit_actions: list[PostSubmitAction] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "transport_id": self.transport_id,
            "interaction_type": self.interaction_type,
            "prompt": self.prompt,
            "status": self.status,
            "created_at": self.created_at,
            "post_submit_actions": [
                action.to_dict() for action in self.post_submit_actions
            ],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> InteractionRequest:
        actions = payload.get("post_submit_actions")
        metadata = payload.get("metadata")
        return cls(
            request_id=str(payload.get("request_id", "")),
            session_id=str(payload.get("session_id", "")),
            transport_id=str(payload.get("transport_id", "")),
            interaction_type=str(payload.get("interaction_type", "")),
            prompt=str(payload.get("prompt", "")),
            status=str(payload.get("status", "pending")),
            created_at=str(payload.get("created_at", "")),
            post_submit_actions=[
                PostSubmitAction.from_dict(item)
                for item in actions
                if isinstance(item, dict)
            ]
            if isinstance(actions, list)
            else [],
            metadata=dict(metadata) if isinstance(metadata, dict) else {},
        )


@dataclass(frozen=True)
class InteractionResult:
    request_id: str
    status: str
    logs: list[str] = field(default_factory=list)
    resume_payload: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "logs": list(self.logs),
            "resume_payload": dict(self.resume_payload),
        }


@dataclass(frozen=True)
class ApprovalRequest:
    request_id: str
    session_id: str
    transport_id: str
    action_label: str
    prompt: str
    status: str
    created_at: str
    action: PostSubmitAction
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "transport_id": self.transport_id,
            "action_label": self.action_label,
            "prompt": self.prompt,
            "status": self.status,
            "created_at": self.created_at,
            "action": self.action.to_dict(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ApprovalRequest:
        action = payload.get("action", {})
        metadata = payload.get("metadata")
        return cls(
            request_id=str(payload.get("request_id", "")),
            session_id=str(payload.get("session_id", "")),
            transport_id=str(payload.get("transport_id", "")),
            action_label=str(payload.get("action_label", "")),
            prompt=str(payload.get("prompt", "")),
            status=str(payload.get("status", "pending")),
            created_at=str(payload.get("created_at", "")),
            action=PostSubmitAction.from_dict(action)
            if isinstance(action, dict)
            else PostSubmitAction(action_type=""),
            metadata=dict(metadata) if isinstance(metadata, dict) else {},
        )


@dataclass(frozen=True)
class ApprovalResult:
    request_id: str
    decision: str
    status: str
    logs: list[str] = field(default_factory=list)
    resume_payload: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "decision": self.decision,
            "status": self.status,
            "logs": list(self.logs),
            "resume_payload": dict(self.resume_payload),
        }
