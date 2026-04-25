from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nagient.domain.entities.system_state import CheckIssue


@dataclass(frozen=True)
class ToolFunctionManifest:
    function_name: str
    binding: str
    description: str
    input_schema: dict[str, object] = field(default_factory=dict)
    output_schema: dict[str, object] = field(default_factory=dict)
    permissions: list[str] = field(default_factory=list)
    required_config: list[str] = field(default_factory=list)
    optional_config: list[str] = field(default_factory=list)
    secret_bindings: list[str] = field(default_factory=list)
    required_connectors: list[str] = field(default_factory=list)
    side_effect: str = "read"
    approval_policy: str = "never"
    dry_run_supported: bool = False

    @property
    def allowed_config(self) -> set[str]:
        return set(self.required_config) | set(self.optional_config)

    def to_dict(self) -> dict[str, object]:
        return {
            "function_name": self.function_name,
            "binding": self.binding,
            "description": self.description,
            "input_schema": dict(self.input_schema),
            "output_schema": dict(self.output_schema),
            "permissions": list(self.permissions),
            "required_config": list(self.required_config),
            "optional_config": list(self.optional_config),
            "secret_bindings": list(self.secret_bindings),
            "required_connectors": list(self.required_connectors),
            "side_effect": self.side_effect,
            "approval_policy": self.approval_policy,
            "dry_run_supported": self.dry_run_supported,
        }


@dataclass(frozen=True)
class ToolPluginManifest:
    plugin_id: str
    display_name: str
    version: str
    namespace: str
    entrypoint: str
    functions: list[ToolFunctionManifest] = field(default_factory=list)
    required_config: list[str] = field(default_factory=list)
    optional_config: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    healthcheck_binding: str | None = None
    selftest_binding: str | None = None
    config_schema_file: str | None = None

    @property
    def allowed_config(self) -> set[str]:
        return set(self.required_config) | set(self.optional_config)

    @property
    def exposed_functions(self) -> list[str]:
        return sorted(function.function_name for function in self.functions)

    def function_by_name(self, function_name: str) -> ToolFunctionManifest | None:
        for function in self.functions:
            if function.function_name == function_name:
                return function
        return None


@dataclass(frozen=True)
class ToolState:
    tool_id: str
    plugin_id: str
    enabled: bool
    status: str
    exposed_functions: list[str] = field(default_factory=list)
    issues: list[CheckIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "tool_id": self.tool_id,
            "plugin_id": self.plugin_id,
            "enabled": self.enabled,
            "status": self.status,
            "exposed_functions": list(self.exposed_functions),
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class ToolExecutionRequest:
    tool_id: str
    function_name: str
    arguments: dict[str, object] = field(default_factory=dict)
    dry_run: bool = False
    batch_id: str | None = None
    session_id: str | None = None
    transport_id: str | None = None
    auto_approve: bool = False

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "tool_id": self.tool_id,
            "function_name": self.function_name,
            "arguments": dict(self.arguments),
            "dry_run": self.dry_run,
            "auto_approve": self.auto_approve,
        }
        if self.batch_id is not None:
            payload["batch_id"] = self.batch_id
        if self.session_id is not None:
            payload["session_id"] = self.session_id
        if self.transport_id is not None:
            payload["transport_id"] = self.transport_id
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ToolExecutionRequest:
        return cls(
            tool_id=str(payload.get("tool_id", "")),
            function_name=str(payload.get("function_name", "")),
            arguments=dict(payload.get("arguments", {}))
            if isinstance(payload.get("arguments"), dict)
            else {},
            dry_run=bool(payload.get("dry_run", False)),
            batch_id=str(payload["batch_id"]) if "batch_id" in payload else None,
            session_id=str(payload["session_id"]) if "session_id" in payload else None,
            transport_id=(
                str(payload["transport_id"]) if "transport_id" in payload else None
            ),
            auto_approve=bool(payload.get("auto_approve", False)),
        )


@dataclass(frozen=True)
class ToolExecutionResult:
    tool_id: str
    function_name: str
    status: str
    output: dict[str, Any] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)
    issues: list[CheckIssue] = field(default_factory=list)
    checkpoint_id: str | None = None
    interaction_request_id: str | None = None
    approval_request_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "tool_id": self.tool_id,
            "function_name": self.function_name,
            "status": self.status,
            "output": dict(self.output),
            "logs": list(self.logs),
            "issues": [issue.to_dict() for issue in self.issues],
        }
        if self.checkpoint_id is not None:
            payload["checkpoint_id"] = self.checkpoint_id
        if self.interaction_request_id is not None:
            payload["interaction_request_id"] = self.interaction_request_id
        if self.approval_request_id is not None:
            payload["approval_request_id"] = self.approval_request_id
        return payload
