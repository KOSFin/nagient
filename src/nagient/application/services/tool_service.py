from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from nagient.app.configuration import (
    RuntimeConfiguration,
    ToolInstanceConfig,
    load_runtime_configuration,
)
from nagient.app.settings import Settings
from nagient.backups.manager import BackupManager
from nagient.domain.entities.agent_runtime import AssistantResponse
from nagient.domain.entities.security import ApprovalRequest, PostSubmitAction
from nagient.domain.entities.system_state import CheckIssue
from nagient.domain.entities.tooling import ToolExecutionRequest, ToolExecutionResult, ToolState
from nagient.security.broker import SecretBroker
from nagient.tools.base import (
    LoadedToolPlugin,
    ToolExecutionContext,
    ToolRiskDecision,
)
from nagient.tools.manager import ToolManager
from nagient.tools.registry import ToolPluginRegistry
from nagient.workspace.manager import WorkspaceLayout, WorkspaceManager


@dataclass
class ToolService:
    settings: Settings
    tool_registry: ToolPluginRegistry
    tool_manager: ToolManager
    secret_broker: SecretBroker
    workspace_manager: WorkspaceManager
    backup_manager: BackupManager
    workflow_service: Any
    transport_router: Any | None = None
    memory_service: Any | None = None
    scheduler_service: Any | None = None
    logger: Any | None = None
    reconcile_runner: Callable[[], dict[str, object]] | None = None

    def list_tools(self) -> dict[str, object]:
        runtime_config = load_runtime_configuration(self.settings)
        discovery = self.tool_registry.discover(self.settings.tools_dir)
        tools: list[ToolState] = []
        for tool in runtime_config.tools:
            plugin = discovery.plugins.get(tool.plugin_id)
            if plugin is None:
                tools.append(
                    ToolState(
                        tool_id=tool.tool_id,
                        plugin_id=tool.plugin_id,
                        enabled=tool.enabled,
                        status="failed" if tool.enabled else "disabled",
                        exposed_functions=[],
                        issues=[
                            CheckIssue(
                                severity="error" if tool.enabled else "warning",
                                code="tool.plugin_not_found",
                                message=(
                                    f"Tool {tool.tool_id!r} references unknown plugin "
                                    f"{tool.plugin_id!r}."
                                ),
                                source=tool.tool_id,
                            )
                        ],
                    )
                )
                continue
            tools.append(self._inspect_tool(runtime_config, tool, discovery.plugins))
        return {
            "tools": [tool.to_dict() for tool in tools],
            "plugins": [
                {
                    "plugin_id": plugin.manifest.plugin_id,
                    "display_name": plugin.manifest.display_name,
                    "namespace": plugin.manifest.namespace,
                    "source": plugin.source,
                    "config_fields": [
                        field_spec.to_dict() for field_spec in plugin.manifest.config_fields
                    ],
                    "functions": [function.to_dict() for function in plugin.manifest.functions],
                }
                for plugin in discovery.plugins.values()
            ],
            "issues": [issue.to_dict() for issue in discovery.issues],
        }

    def invoke(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        results, _ = self.invoke_batch([request])
        return results[0]

    def invoke_from_dict(self, payload: dict[str, object]) -> dict[str, object]:
        return self.invoke(ToolExecutionRequest.from_dict(payload)).to_dict()

    def invoke_batch(
        self,
        requests: list[ToolExecutionRequest],
    ) -> tuple[list[ToolExecutionResult], str | None]:
        runtime_config = load_runtime_configuration(self.settings)
        layout = self.workspace_manager.ensure_layout(runtime_config.workspace)
        discovery = self.tool_registry.discover(self.settings.tools_dir)
        self._log(
            "debug",
            "tool.invoke_batch.start",
            "Preparing tool batch execution.",
            requests=len(requests),
            workspace_id=layout.metadata.workspace_id,
        )

        prepared: list[
            tuple[
                ToolExecutionRequest,
                ToolInstanceConfig,
                LoadedToolPlugin,
                ToolRiskDecision,
                bool,
                str,
            ]
        ] = []
        checkpoint_required = False
        for request in requests:
            tool_config, plugin = self._resolve_tool(runtime_config, discovery.plugins, request)
            function = plugin.manifest.function_by_name(request.function_name)
            if function is None:
                raise ValueError(
                    f"Tool plugin {plugin.manifest.plugin_id!r} does not expose function "
                    f"{request.function_name!r}."
                )
            context = self._build_context(
                layout=layout,
                tool_config=tool_config,
                plugin_id=plugin.manifest.plugin_id,
                request=request,
                checkpoint_id=None,
            )
            risk = plugin.implementation.assess_risk(
                request.function_name,
                request.arguments,
                context,
            )
            effective_policy = function.approval_policy
            if risk.approval_policy != "inherit":
                effective_policy = risk.approval_policy
            needs_checkpoint = (
                risk.checkpoint_required
                if risk.checkpoint_required is not None
                else function.side_effect in {"write", "destructive", "system"}
            )
            checkpoint_required = checkpoint_required or (
                needs_checkpoint
                and not request.dry_run
                and not (effective_policy == "required" and not request.auto_approve)
            )
            prepared.append(
                (request, tool_config, plugin, risk, needs_checkpoint, effective_policy)
            )

        checkpoint_id: str | None = None
        if checkpoint_required:
            try:
                checkpoint_id = self.backup_manager.create_snapshot(
                    layout,
                    reason="tool-execution-batch",
                ).snapshot_id
                self._log(
                    "info",
                    "tool.invoke_batch.checkpoint_created",
                    "Created workspace checkpoint for tool batch.",
                    checkpoint_id=checkpoint_id,
                    workspace_id=layout.metadata.workspace_id,
                )
            except Exception as exc:
                self._log(
                    "error",
                    "tool.invoke_batch.checkpoint_failed",
                    "Failed to create workspace checkpoint for tool batch.",
                    error=str(exc),
                    workspace_id=layout.metadata.workspace_id,
                )
                return (
                    [
                        ToolExecutionResult(
                            tool_id=request.tool_id or tool_config.tool_id,
                            function_name=request.function_name,
                            status="failed",
                            issues=[
                                CheckIssue(
                                    severity="error",
                                    code="tool.checkpoint_failed",
                                    message=self.secret_broker.redact_text(str(exc)),
                                    source=tool_config.tool_id,
                                )
                            ],
                        )
                        for (
                            request,
                            tool_config,
                            _plugin,
                            _risk,
                            _needs_checkpoint,
                            _policy,
                        ) in prepared
                    ],
                    None,
                )

        results: list[ToolExecutionResult] = []
        for request, tool_config, plugin, risk, needs_checkpoint, effective_policy in prepared:
            function = plugin.manifest.function_by_name(request.function_name)
            if function is None:
                raise AssertionError("Function was resolved during preparation.")
            if effective_policy == "required" and not request.auto_approve:
                approval = self.workflow_service.create_approval(
                    ApprovalRequest(
                        request_id="",
                        session_id=request.session_id or "system",
                        transport_id=request.transport_id or "console",
                        action_label=request.function_name,
                        prompt=(
                            risk.reason
                            or f"Approve execution of {request.function_name!r}?"
                        ),
                        status="pending",
                        created_at="",
                        action=PostSubmitAction(
                            action_type="tool.invoke",
                            payload={
                                **request.to_dict(),
                                "auto_approve": True,
                            },
                        ),
                    )
                )
                results.append(
                    ToolExecutionResult(
                        tool_id=tool_config.tool_id,
                        function_name=request.function_name,
                        status="approval_required",
                        approval_request_id=approval.request_id,
                        checkpoint_id=checkpoint_id if needs_checkpoint else None,
                        output={},
                    )
                )
                self._log(
                    "info",
                    "tool.invoke_batch.approval_requested",
                    "Queued tool execution for approval.",
                    tool_id=tool_config.tool_id,
                    function_name=request.function_name,
                )
                continue

            context = self._build_context(
                layout=layout,
                tool_config=tool_config,
                plugin_id=plugin.manifest.plugin_id,
                request=request,
                checkpoint_id=checkpoint_id if needs_checkpoint else None,
            )
            self._log(
                "info",
                "tool.invoke_batch.executing",
                "Executing tool function.",
                tool_id=tool_config.tool_id,
                function_name=request.function_name,
                argument_keys=sorted(request.arguments),
                checkpoint_id=checkpoint_id if needs_checkpoint else None,
                dry_run=request.dry_run,
            )
            try:
                output = plugin.implementation.execute(
                    request.function_name,
                    request.arguments,
                    context,
                )
                sanitized_output = self.secret_broker.redact_value(output)
                interaction_request_id = None
                if (
                    plugin.manifest.plugin_id == "transport.interaction"
                    and isinstance(sanitized_output, dict)
                ):
                    interaction_request_id = str(sanitized_output.get("request_id", "")) or None
                results.append(
                    ToolExecutionResult(
                        tool_id=tool_config.tool_id,
                        function_name=request.function_name,
                        status="success",
                        output=sanitized_output if isinstance(sanitized_output, dict) else {},
                        checkpoint_id=checkpoint_id if needs_checkpoint else None,
                        interaction_request_id=interaction_request_id,
                    )
                )
                self._log(
                    "info",
                    "tool.invoke_batch.success",
                    "Executed tool function successfully.",
                    tool_id=tool_config.tool_id,
                    function_name=request.function_name,
                    checkpoint_id=checkpoint_id if needs_checkpoint else None,
                    output_summary=_summarize_tool_output(sanitized_output),
                )
            except Exception as exc:
                self._log(
                    "error",
                    "tool.invoke_batch.failed",
                    "Tool function execution failed.",
                    tool_id=tool_config.tool_id,
                    function_name=request.function_name,
                    error=str(exc),
                )
                results.append(
                    ToolExecutionResult(
                        tool_id=tool_config.tool_id,
                        function_name=request.function_name,
                        status="failed",
                        issues=[
                            CheckIssue(
                                severity="error",
                                code="tool.execution_failed",
                                message=self.secret_broker.redact_text(str(exc)),
                                source=tool_config.tool_id,
                            )
                        ],
                        checkpoint_id=checkpoint_id if needs_checkpoint else None,
                    )
                )

        self._log(
            "debug",
            "tool.invoke_batch.completed",
            "Completed tool batch execution.",
            requests=len(requests),
            results=len(results),
            checkpoint_id=checkpoint_id,
        )
        return results, checkpoint_id

    def _inspect_tool(
        self,
        runtime_config: RuntimeConfiguration,
        tool: ToolInstanceConfig,
        plugins: dict[str, LoadedToolPlugin],
    ) -> ToolState:
        plugin = plugins[tool.plugin_id]
        del runtime_config
        return self.tool_manager.inspect_tool(tool, plugin, self.secret_broker)

    def _resolve_tool(
        self,
        runtime_config: RuntimeConfiguration,
        plugins: dict[str, LoadedToolPlugin],
        request: ToolExecutionRequest,
    ) -> tuple[ToolInstanceConfig, LoadedToolPlugin]:
        tool_config = next(
            (
                tool
                for tool in runtime_config.tools
                if tool.tool_id == request.tool_id or tool.plugin_id == request.tool_id
            ),
            None,
        )
        if tool_config is None:
            inferred_plugin_id = ".".join(request.function_name.split(".")[:-1])
            tool_config = next(
                (tool for tool in runtime_config.tools if tool.plugin_id == inferred_plugin_id),
                None,
            )
        if tool_config is None:
            raise ValueError(f"Tool profile {request.tool_id!r} is not configured.")
        plugin = plugins.get(tool_config.plugin_id)
        if plugin is None:
            raise ValueError(
                f"Tool profile {tool_config.tool_id!r} references unknown plugin "
                f"{tool_config.plugin_id!r}."
            )
        if not tool_config.enabled:
            raise ValueError(f"Tool profile {tool_config.tool_id!r} is disabled.")
        return tool_config, plugin

    def _build_context(
        self,
        *,
        layout: WorkspaceLayout,
        tool_config: ToolInstanceConfig,
        plugin_id: str,
        request: ToolExecutionRequest,
        checkpoint_id: str | None,
    ) -> ToolExecutionContext:
        return ToolExecutionContext(
            settings=self.settings,
            workspace=layout,
            workspace_manager=self.workspace_manager,
            tool_id=tool_config.tool_id,
            plugin_id=plugin_id,
            config=tool_config.config,
            secret_broker=self.secret_broker,
            backup_manager=self.backup_manager,
            request_interaction=self.workflow_service.create_interaction,
            request_approval=self.workflow_service.create_approval,
            invoke_reconcile=self._invoke_reconcile,
            invoke_assistant_resume=self._invoke_assistant_resume,
            transport_router=self.transport_router,
            memory_service=self.memory_service,
            scheduler_service=self.scheduler_service,
            logger=self.logger,
            dry_run=request.dry_run,
            session_id=request.session_id,
            transport_id=request.transport_id,
            checkpoint_id=checkpoint_id,
        )

    def _invoke_reconcile(self) -> dict[str, object]:
        if self.reconcile_runner is None:
            return {"status": "skipped", "message": "Reconcile runner is not configured."}
        return self.reconcile_runner()

    def _invoke_assistant_resume(self, assistant_response: AssistantResponse) -> dict[str, object]:
        return {
            "assistant_response": assistant_response.to_dict(),
            "status": "queued",
        }

    def _log(
        self,
        level: str,
        event: str,
        message: str,
        **fields: object,
    ) -> None:
        if self.logger is None:
            return
        log_method = getattr(self.logger, level, None)
        if callable(log_method):
            log_method(event, message, **fields)


def _summarize_tool_output(output: object) -> dict[str, object]:
    if not isinstance(output, dict):
        return {}

    summary: dict[str, object] = {"keys": sorted(output)[:8]}
    scalar_keys = [
        "status",
        "message",
        "chat_id",
        "message_id",
        "request_id",
        "exit_code",
        "timed_out",
        "blocked",
        "blocked_reason",
    ]
    for key in scalar_keys:
        value = output.get(key)
        if isinstance(value, (str, int, float, bool)) and str(value).strip():
            summary[key] = value

    if isinstance(output.get("results"), list):
        summary["results_count"] = len(output["results"])
    if isinstance(output.get("notes"), list):
        summary["notes_count"] = len(output["notes"])
    if isinstance(output.get("transports"), list):
        summary["transports_count"] = len(output["transports"])

    stdout = output.get("stdout")
    if isinstance(stdout, str) and stdout.strip():
        summary["stdout_preview"] = _compact_preview(stdout, limit=160)
    stderr = output.get("stderr")
    if isinstance(stderr, str) and stderr.strip():
        summary["stderr_preview"] = _compact_preview(stderr, limit=160)
    return summary


def _compact_preview(value: str, *, limit: int) -> str:
    stripped = value.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[:limit].rstrip() + "..."
