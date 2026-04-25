from __future__ import annotations

from dataclasses import dataclass, field

from nagient.domain.entities.system_state import CheckIssue


@dataclass(frozen=True)
class WorkspaceMetadata:
    workspace_id: str
    root: str
    mode: str
    nagient_dir: str
    created_at: str
    updated_at: str
    policy: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "workspace_id": self.workspace_id,
            "root": self.root,
            "mode": self.mode,
            "nagient_dir": self.nagient_dir,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "policy": dict(self.policy),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> WorkspaceMetadata:
        policy = payload.get("policy")
        return cls(
            workspace_id=str(payload.get("workspace_id", "")),
            root=str(payload.get("root", "")),
            mode=str(payload.get("mode", "bounded")),
            nagient_dir=str(payload.get("nagient_dir", "")),
            created_at=str(payload.get("created_at", "")),
            updated_at=str(payload.get("updated_at", "")),
            policy=dict(policy) if isinstance(policy, dict) else {},
        )


@dataclass(frozen=True)
class WorkspaceState:
    workspace_id: str
    root: str
    mode: str
    nagient_dir: str
    status: str
    backup_enabled: bool
    issues: list[CheckIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "workspace_id": self.workspace_id,
            "root": self.root,
            "mode": self.mode,
            "nagient_dir": self.nagient_dir,
            "status": self.status,
            "backup_enabled": self.backup_enabled,
            "issues": [issue.to_dict() for issue in self.issues],
        }
