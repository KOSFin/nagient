from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from nagient.app.configuration import read_raw_config
from nagient.app.settings import Settings
from nagient.domain.entities.agent_runtime import AssistantResponse
from nagient.domain.entities.security import (
    ApprovalRequest,
    ApprovalResult,
    InteractionRequest,
    InteractionResult,
    PostSubmitAction,
)
from nagient.security.broker import SecretBroker
from nagient.security.workflows import WorkflowStore


@dataclass
class WorkflowService:
    settings: Settings
    workflow_store: WorkflowStore
    secret_broker: SecretBroker
    backup_restorer: Callable[[str], dict[str, object]]
    reconcile_runner: Callable[[], dict[str, object]]
    assistant_resume_handler: Callable[[AssistantResponse], dict[str, object]]
    tool_invoker: Callable[[dict[str, object]], dict[str, object]] | None = None

    def create_interaction(self, request: InteractionRequest) -> InteractionRequest:
        return self.workflow_store.save_interaction(request)

    def list_interactions(self) -> list[InteractionRequest]:
        return self.workflow_store.list_interactions()

    def submit_interaction(
        self,
        request_id: str,
        *,
        response: str | None = None,
        cancel: bool = False,
    ) -> InteractionResult:
        request = self.workflow_store.load_interaction(request_id)
        if request is None:
            raise ValueError(f"Interaction request {request_id!r} was not found.")
        if cancel:
            cancelled = InteractionRequest(
                request_id=request.request_id,
                session_id=request.session_id,
                transport_id=request.transport_id,
                interaction_type=request.interaction_type,
                prompt=request.prompt,
                status="cancelled",
                created_at=request.created_at,
                post_submit_actions=request.post_submit_actions,
                metadata=request.metadata,
            )
            self.workflow_store.save_interaction(cancelled)
            return InteractionResult(request_id=request_id, status="cancelled", logs=[])

        logs: list[str] = []
        resume_payload: dict[str, object] = {}
        status = "success"
        try:
            logs, resume_payload = self._execute_actions(
                request.post_submit_actions,
                response=response,
                session_id=request.session_id,
                transport_id=request.transport_id,
            )
        except Exception as exc:
            status = "failed"
            logs.append(str(exc))

        completed = InteractionRequest(
            request_id=request.request_id,
            session_id=request.session_id,
            transport_id=request.transport_id,
            interaction_type=request.interaction_type,
            prompt=request.prompt,
            status=status,
            created_at=request.created_at,
            post_submit_actions=request.post_submit_actions,
            metadata=request.metadata,
        )
        self.workflow_store.save_interaction(completed)
        sanitized_resume = self.secret_broker.redact_value(resume_payload)
        return InteractionResult(
            request_id=request_id,
            status=status,
            logs=[self.secret_broker.redact_text(log) for log in logs],
            resume_payload=sanitized_resume if isinstance(sanitized_resume, dict) else {},
        )

    def create_approval(self, request: ApprovalRequest) -> ApprovalRequest:
        return self.workflow_store.save_approval(request)

    def list_approvals(self) -> list[ApprovalRequest]:
        return self.workflow_store.list_approvals()

    def resolve_approval(self, request_id: str, decision: str) -> ApprovalResult:
        request = self.workflow_store.load_approval(request_id)
        if request is None:
            raise ValueError(f"Approval request {request_id!r} was not found.")

        if decision not in {"approve", "reject", "cancel"}:
            raise ValueError("Approval decision must be approve, reject, or cancel.")

        logs: list[str] = []
        resume_payload: dict[str, object] = {}
        status = decision
        if decision == "approve":
            try:
                logs, resume_payload = self._execute_actions(
                    [request.action],
                    response=None,
                    session_id=request.session_id,
                    transport_id=request.transport_id,
                )
                status = "approved"
            except Exception as exc:
                status = "failed"
                logs.append(str(exc))

        stored = ApprovalRequest(
            request_id=request.request_id,
            session_id=request.session_id,
            transport_id=request.transport_id,
            action_label=request.action_label,
            prompt=request.prompt,
            status=status,
            created_at=request.created_at,
            action=request.action,
            metadata=request.metadata,
        )
        self.workflow_store.save_approval(stored)
        sanitized_resume = self.secret_broker.redact_value(resume_payload)
        return ApprovalResult(
            request_id=request_id,
            decision=decision,
            status=status,
            logs=[self.secret_broker.redact_text(log) for log in logs],
            resume_payload=sanitized_resume if isinstance(sanitized_resume, dict) else {},
        )

    def _execute_actions(
        self,
        actions: list[PostSubmitAction],
        *,
        response: str | None,
        session_id: str,
        transport_id: str,
    ) -> tuple[list[str], dict[str, object]]:
        logs: list[str] = []
        resume_payload: dict[str, object] = {}
        for action in actions:
            if action.action_type == "secret.store":
                if response is None:
                    raise ValueError("Interaction response is required for secret.store.")
                secret_name = _require_string(action.payload, "secret_name")
                scope = str(action.payload.get("scope", "tool"))
                bindings_payload = action.payload.get("bindings", [])
                self.secret_broker.store_secret(
                    secret_name,
                    response,
                    scope=scope,
                )
                if isinstance(bindings_payload, list):
                    for item in bindings_payload:
                        if not isinstance(item, dict):
                            continue
                        target_id = str(item.get("target_id", ""))
                        if not target_id:
                            continue
                        self.secret_broker.bind_secret(
                            secret_name,
                            target_kind=str(item.get("target_kind", "tool")),
                            target_id=target_id,
                            scope_hint=scope,
                        )
                logs.append(f"Stored secret {secret_name!r} in {scope!r} scope.")
                continue

            if action.action_type == "connector.bind_secret":
                secret_name = _require_string(action.payload, "secret_name")
                target_kind = _require_string(action.payload, "target_kind")
                target_id = _require_string(action.payload, "target_id")
                scope_hint = str(action.payload.get("scope_hint", "tool"))
                self.secret_broker.bind_secret(
                    secret_name,
                    target_kind=target_kind,
                    target_id=target_id,
                    scope_hint=scope_hint,
                )
                logs.append(f"Bound secret {secret_name!r} to {target_kind}:{target_id}.")
                continue

            if action.action_type == "config.patch":
                config_path = _require_string(action.payload, "path")
                config_value = action.payload.get("value")
                _patch_config_file(self.settings.config_file, config_path, config_value)
                logs.append(f"Patched config at {config_path!r}.")
                continue

            if action.action_type == "tool.invoke":
                if self.tool_invoker is None:
                    raise ValueError("Tool invocation is not wired for workflow execution.")
                tool_payload = dict(action.payload)
                tool_payload.setdefault("session_id", session_id)
                tool_payload.setdefault("transport_id", transport_id)
                tool_payload["auto_approve"] = True
                result = self.tool_invoker(tool_payload)
                logs.append(f"Executed tool action {tool_payload.get('function_name', '')!r}.")
                resume_payload["tool_result"] = result
                continue

            if action.action_type == "backup.restore":
                snapshot_id = _require_string(action.payload, "snapshot_id")
                result = self.backup_restorer(snapshot_id)
                logs.append(f"Restored backup snapshot {snapshot_id!r}.")
                resume_payload["backup_restore"] = result
                continue

            if action.action_type == "system.reconcile":
                result = self.reconcile_runner()
                logs.append("Ran reconcile after workflow submission.")
                resume_payload["reconcile"] = result
                continue

            if action.action_type == "agent.resume":
                assistant_response = AssistantResponse.from_dict(action.payload)
                resume_payload["assistant_resume"] = self.assistant_resume_handler(
                    assistant_response
                )
                logs.append("Prepared assistant resume payload.")
                continue

            if action.action_type == "agent.resume_with_error":
                resume_payload["assistant_resume_error"] = {
                    "status": "failed",
                    "error": str(action.payload.get("error", "workflow failed")),
                }
                logs.append("Prepared assistant resume error payload.")
                continue

            raise ValueError(f"Unsupported workflow action type {action.action_type!r}.")

        return logs, resume_payload


def _require_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Workflow action field {key!r} must be a non-empty string.")
    return value


def _patch_config_file(config_file: Path, dotted_path: str, value: object) -> None:
    payload = read_raw_config(config_file)
    parts = [part for part in dotted_path.split(".") if part]
    if not parts:
        raise ValueError("Config patch path must not be empty.")

    current: dict[str, object] = payload
    for part in parts[:-1]:
        nested = current.get(part)
        if not isinstance(nested, dict):
            nested = {}
            current[part] = nested
        current = nested
    current[parts[-1]] = value
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(_render_toml(payload), encoding="utf-8")


def _render_toml(payload: dict[str, object]) -> str:
    lines: list[str] = []
    _render_table(lines, payload, prefix=[])
    return "\n".join(lines).rstrip() + "\n"


def _render_table(lines: list[str], payload: dict[str, object], prefix: list[str]) -> None:
    scalar_items = [
        (key, value) for key, value in payload.items() if not isinstance(value, dict)
    ]
    nested_items = [
        (key, value) for key, value in payload.items() if isinstance(value, dict)
    ]
    if prefix:
        lines.append(f"[{'.'.join(prefix)}]")
    for key, value in scalar_items:
        lines.append(f"{key} = {_render_toml_value(value)}")
    if scalar_items and nested_items:
        lines.append("")
    for index, (key, value) in enumerate(nested_items):
        _render_table(lines, value, prefix=[*prefix, key])
        if index != len(nested_items) - 1:
            lines.append("")


def _render_toml_value(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, list):
        rendered = ", ".join(_render_toml_value(item) for item in value)
        return f"[{rendered}]"
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
