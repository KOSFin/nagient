from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nagient.domain.entities.tooling import ToolState
    from nagient.domain.entities.workspace import WorkspaceState


@dataclass(frozen=True)
class CheckIssue:
    severity: str
    code: str
    message: str
    source: str = "system"
    hint: str | None = None

    def to_dict(self) -> dict[str, str]:
        payload = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "source": self.source,
        }
        if self.hint:
            payload["hint"] = self.hint
        return payload


@dataclass(frozen=True)
class TransportState:
    transport_id: str
    plugin_id: str
    enabled: bool
    status: str
    exposed_functions: list[str] = field(default_factory=list)
    issues: list[CheckIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "transport_id": self.transport_id,
            "plugin_id": self.plugin_id,
            "enabled": self.enabled,
            "status": self.status,
            "exposed_functions": self.exposed_functions,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class ProviderAuthStatus:
    authenticated: bool
    auth_mode: str
    status: str
    message: str
    issues: list[CheckIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "authenticated": self.authenticated,
            "auth_mode": self.auth_mode,
            "status": self.status,
            "message": self.message,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class ProviderModel:
    model_id: str
    display_name: str
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CredentialRecord:
    provider_id: str
    plugin_id: str
    auth_mode: str
    data: dict[str, object] = field(default_factory=dict)
    issued_at: str | None = None
    expires_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "provider_id": self.provider_id,
            "plugin_id": self.plugin_id,
            "auth_mode": self.auth_mode,
            "data": dict(self.data),
        }
        if self.issued_at is not None:
            payload["issued_at"] = self.issued_at
        if self.expires_at is not None:
            payload["expires_at"] = self.expires_at
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> CredentialRecord:
        data = payload.get("data", {})
        return cls(
            provider_id=str(payload.get("provider_id", "")),
            plugin_id=str(payload.get("plugin_id", "")),
            auth_mode=str(payload.get("auth_mode", "")),
            data=dict(data) if isinstance(data, dict) else {},
            issued_at=str(payload["issued_at"]) if "issued_at" in payload else None,
            expires_at=str(payload["expires_at"]) if "expires_at" in payload else None,
        )


@dataclass(frozen=True)
class AuthSessionState:
    session_id: str
    provider_id: str
    plugin_id: str
    auth_mode: str
    status: str
    submission_mode: str
    instructions: list[str] = field(default_factory=list)
    authorization_url: str | None = None
    user_code: str | None = None
    callback_url: str | None = None
    expires_at: str | None = None
    poll_interval_seconds: int | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "session_id": self.session_id,
            "provider_id": self.provider_id,
            "plugin_id": self.plugin_id,
            "auth_mode": self.auth_mode,
            "status": self.status,
            "submission_mode": self.submission_mode,
            "instructions": list(self.instructions),
            "metadata": dict(self.metadata),
        }
        if self.authorization_url is not None:
            payload["authorization_url"] = self.authorization_url
        if self.user_code is not None:
            payload["user_code"] = self.user_code
        if self.callback_url is not None:
            payload["callback_url"] = self.callback_url
        if self.expires_at is not None:
            payload["expires_at"] = self.expires_at
        if self.poll_interval_seconds is not None:
            payload["poll_interval_seconds"] = self.poll_interval_seconds
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> AuthSessionState:
        metadata = payload.get("metadata", {})
        instructions = payload.get("instructions", [])
        poll_interval_seconds = payload.get("poll_interval_seconds")
        return cls(
            session_id=str(payload.get("session_id", "")),
            provider_id=str(payload.get("provider_id", "")),
            plugin_id=str(payload.get("plugin_id", "")),
            auth_mode=str(payload.get("auth_mode", "")),
            status=str(payload.get("status", "")),
            submission_mode=str(payload.get("submission_mode", "")),
            instructions=(
                [str(item) for item in instructions]
                if isinstance(instructions, list)
                else []
            ),
            authorization_url=(
                str(payload["authorization_url"])
                if "authorization_url" in payload
                else None
            ),
            user_code=str(payload["user_code"]) if "user_code" in payload else None,
            callback_url=str(payload["callback_url"]) if "callback_url" in payload else None,
            expires_at=str(payload["expires_at"]) if "expires_at" in payload else None,
            poll_interval_seconds=(
                int(poll_interval_seconds)
                if isinstance(poll_interval_seconds, int)
                else None
            ),
            metadata=dict(metadata) if isinstance(metadata, dict) else {},
        )


@dataclass(frozen=True)
class ProviderState:
    provider_id: str
    plugin_id: str
    enabled: bool
    default: bool
    status: str
    authenticated: bool
    auth_mode: str
    auth_message: str
    configured_model: str | None = None
    capabilities: list[str] = field(default_factory=list)
    issues: list[CheckIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "provider_id": self.provider_id,
            "plugin_id": self.plugin_id,
            "enabled": self.enabled,
            "default": self.default,
            "status": self.status,
            "authenticated": self.authenticated,
            "auth_mode": self.auth_mode,
            "auth_message": self.auth_message,
            "capabilities": list(self.capabilities),
            "issues": [issue.to_dict() for issue in self.issues],
        }
        if self.configured_model is not None:
            payload["configured_model"] = self.configured_model
        return payload


@dataclass(frozen=True)
class ActivationReport:
    status: str
    safe_mode: bool
    can_activate: bool
    transports: list[TransportState] = field(default_factory=list)
    providers: list[ProviderState] = field(default_factory=list)
    tools: list[ToolState] = field(default_factory=list)
    workspace: WorkspaceState | None = None
    issues: list[CheckIssue] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    effective_config: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "safe_mode": self.safe_mode,
            "can_activate": self.can_activate,
            "transports": [transport.to_dict() for transport in self.transports],
            "providers": [provider.to_dict() for provider in self.providers],
            "tools": [tool.to_dict() for tool in self.tools],
            "workspace": self.workspace.to_dict() if self.workspace is not None else None,
            "issues": [issue.to_dict() for issue in self.issues],
            "notices": list(self.notices),
            "effective_config": dict(self.effective_config),
        }
