from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from nagient.app.configuration import workflow_state_dir
from nagient.app.settings import Settings
from nagient.domain.entities.security import ApprovalRequest, InteractionRequest


@dataclass(frozen=True)
class WorkflowStore:
    settings: Settings

    def save_interaction(self, request: InteractionRequest) -> InteractionRequest:
        stored = InteractionRequest(
            request_id=request.request_id or f"int_{uuid.uuid4().hex}",
            session_id=request.session_id,
            transport_id=request.transport_id,
            interaction_type=request.interaction_type,
            prompt=request.prompt,
            status=request.status or "pending",
            created_at=request.created_at or _utc_now(),
            post_submit_actions=request.post_submit_actions,
            metadata=request.metadata,
        )
        path = self._interactions_dir() / f"{stored.request_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(stored.to_dict(), indent=2) + "\n", encoding="utf-8")
        return stored

    def load_interaction(self, request_id: str) -> InteractionRequest | None:
        path = self._interactions_dir() / f"{request_id}.json"
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        return InteractionRequest.from_dict(payload)

    def list_interactions(self) -> list[InteractionRequest]:
        if not self._interactions_dir().exists():
            return []
        requests: list[InteractionRequest] = []
        for path in sorted(self._interactions_dir().glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                requests.append(InteractionRequest.from_dict(payload))
        return requests

    def save_approval(self, request: ApprovalRequest) -> ApprovalRequest:
        stored = ApprovalRequest(
            request_id=request.request_id or f"apr_{uuid.uuid4().hex}",
            session_id=request.session_id,
            transport_id=request.transport_id,
            action_label=request.action_label,
            prompt=request.prompt,
            status=request.status or "pending",
            created_at=request.created_at or _utc_now(),
            action=request.action,
            metadata=request.metadata,
        )
        path = self._approvals_dir() / f"{stored.request_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(stored.to_dict(), indent=2) + "\n", encoding="utf-8")
        return stored

    def load_approval(self, request_id: str) -> ApprovalRequest | None:
        path = self._approvals_dir() / f"{request_id}.json"
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        return ApprovalRequest.from_dict(payload)

    def list_approvals(self) -> list[ApprovalRequest]:
        if not self._approvals_dir().exists():
            return []
        requests: list[ApprovalRequest] = []
        for path in sorted(self._approvals_dir().glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                requests.append(ApprovalRequest.from_dict(payload))
        return requests

    def _interactions_dir(self) -> Path:
        return workflow_state_dir(self.settings) / "interactions"

    def _approvals_dir(self) -> Path:
        return workflow_state_dir(self.settings) / "approvals"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
