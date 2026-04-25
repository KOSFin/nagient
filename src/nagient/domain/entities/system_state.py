from __future__ import annotations

from dataclasses import dataclass, field


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
class ActivationReport:
    status: str
    safe_mode: bool
    can_activate: bool
    transports: list[TransportState] = field(default_factory=list)
    issues: list[CheckIssue] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    effective_config: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "safe_mode": self.safe_mode,
            "can_activate": self.can_activate,
            "transports": [transport.to_dict() for transport in self.transports],
            "issues": [issue.to_dict() for issue in self.issues],
            "notices": list(self.notices),
            "effective_config": dict(self.effective_config),
        }
