from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from nagient.app.settings import Settings
from nagient.domain.entities.agent_runtime import AssistantResponse
from nagient.domain.entities.security import ApprovalRequest, InteractionRequest
from nagient.domain.entities.system_state import CheckIssue
from nagient.domain.entities.tooling import ToolPluginManifest
from nagient.security.broker import SecretBroker
from nagient.workspace.manager import WorkspaceLayout, WorkspaceManager


@dataclass(frozen=True)
class LoadedToolPlugin:
    manifest: ToolPluginManifest
    implementation: BaseToolPlugin
    source: str


@dataclass(frozen=True)
class ToolRiskDecision:
    approval_policy: str
    reason: str | None = None
    checkpoint_required: bool | None = None


@dataclass(frozen=True)
class ToolExecutionContext:
    settings: Settings
    workspace: WorkspaceLayout
    workspace_manager: WorkspaceManager
    tool_id: str
    plugin_id: str
    config: dict[str, object]
    secret_broker: SecretBroker
    backup_manager: object
    request_interaction: Callable[[InteractionRequest], InteractionRequest]
    request_approval: Callable[[ApprovalRequest], ApprovalRequest]
    invoke_reconcile: Callable[[], dict[str, object]]
    invoke_assistant_resume: Callable[[AssistantResponse], dict[str, object]]
    dry_run: bool = False
    session_id: str | None = None
    transport_id: str | None = None
    checkpoint_id: str | None = None


class BaseToolPlugin:
    manifest: ToolPluginManifest

    def validate_config(
        self,
        tool_id: str,
        config: Mapping[str, object],
        secret_broker: SecretBroker,
    ) -> list[CheckIssue]:
        del tool_id, config, secret_broker
        return []

    def self_test(
        self,
        tool_id: str,
        config: Mapping[str, object],
        secret_broker: SecretBroker,
    ) -> list[CheckIssue]:
        del tool_id, config, secret_broker
        return []

    def healthcheck(
        self,
        tool_id: str,
        config: Mapping[str, object],
        secret_broker: SecretBroker,
    ) -> list[CheckIssue]:
        del tool_id, config, secret_broker
        return []

    def assess_risk(
        self,
        function_name: str,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> ToolRiskDecision:
        del function_name, arguments, context
        return ToolRiskDecision(approval_policy="inherit")

    def execute(
        self,
        function_name: str,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        function = self.manifest.function_by_name(function_name)
        if function is None:
            raise ValueError(f"Unknown tool function {function_name!r}.")
        binding = getattr(self, function.binding, None)
        if not callable(binding):
            raise ValueError(
                f"Tool function {function_name!r} is bound to missing method {function.binding!r}."
            )
        result = binding(arguments, context)
        if not isinstance(result, dict):
            raise ValueError(
                f"Tool function {function_name!r} must return a dictionary payload."
            )
        return result
