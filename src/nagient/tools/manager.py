from __future__ import annotations

from dataclasses import dataclass

from nagient.app.configuration import ToolInstanceConfig
from nagient.domain.entities.system_state import CheckIssue
from nagient.domain.entities.tooling import ToolPluginManifest, ToolState
from nagient.security.broker import SecretBroker
from nagient.tools.base import LoadedToolPlugin


@dataclass(frozen=True)
class ToolManager:
    def inspect_tool(
        self,
        tool: ToolInstanceConfig,
        plugin: LoadedToolPlugin,
        secret_broker: SecretBroker,
    ) -> ToolState:
        issues: list[CheckIssue] = []
        manifest = plugin.manifest
        if not tool.enabled:
            return ToolState(
                tool_id=tool.tool_id,
                plugin_id=tool.plugin_id,
                enabled=False,
                status="disabled",
                exposed_functions=manifest.exposed_functions,
                issues=[],
            )

        issues.extend(self._lint_config(tool.tool_id, manifest, tool.config))
        issues.extend(
            self._call_check(tool.tool_id, plugin, "validate_config", tool.config, secret_broker)
        )
        if not any(issue.severity == "error" for issue in issues):
            issues.extend(
                self._call_check(tool.tool_id, plugin, "self_test", tool.config, secret_broker)
            )
            issues.extend(
                self._call_check(tool.tool_id, plugin, "healthcheck", tool.config, secret_broker)
            )

        status = "ready"
        if any(issue.severity == "error" for issue in issues):
            status = "failed"
        elif issues:
            status = "degraded"

        return ToolState(
            tool_id=tool.tool_id,
            plugin_id=tool.plugin_id,
            enabled=True,
            status=status,
            exposed_functions=manifest.exposed_functions,
            issues=issues,
        )

    def _lint_config(
        self,
        tool_id: str,
        manifest: ToolPluginManifest,
        config: dict[str, object],
    ) -> list[CheckIssue]:
        issues: list[CheckIssue] = []
        for field_name in manifest.required_config:
            if field_name not in config:
                issues.append(
                    CheckIssue(
                        severity="error",
                        code="tool.missing_required_config",
                        message=(
                            f"Tool {tool_id!r} must define required field {field_name!r}."
                        ),
                        source=tool_id,
                    )
                )
        unknown_keys = sorted(set(config) - manifest.allowed_config)
        for key in unknown_keys:
            issues.append(
                CheckIssue(
                    severity="warning",
                    code="tool.unknown_config_key",
                    message=f"Tool {tool_id!r} defines unknown config key {key!r}.",
                    source=tool_id,
                )
            )
        return issues

    def _call_check(
        self,
        tool_id: str,
        plugin: LoadedToolPlugin,
        method_name: str,
        config: dict[str, object],
        secret_broker: SecretBroker,
    ) -> list[CheckIssue]:
        method = getattr(plugin.implementation, method_name, None)
        if not callable(method):
            return [
                CheckIssue(
                    severity="error",
                    code="tool.plugin_missing_method",
                    message=(
                        f"Tool plugin {plugin.manifest.plugin_id!r} does not expose "
                        f"method {method_name!r}."
                    ),
                    source=tool_id,
                )
            ]

        try:
            result = method(tool_id, config, secret_broker)
        except Exception as exc:
            return [
                CheckIssue(
                    severity="error",
                    code="tool.plugin_runtime_error",
                    message=(
                        f"Tool plugin {plugin.manifest.plugin_id!r} raised an exception "
                        f"during {method_name}: {exc}"
                    ),
                    source=tool_id,
                )
            ]
        if result is None:
            return []
        if isinstance(result, list) and all(isinstance(item, CheckIssue) for item in result):
            return result
        return [
            CheckIssue(
                severity="error",
                code="tool.plugin_invalid_check_result",
                message=(
                    f"Tool plugin {plugin.manifest.plugin_id!r} returned an invalid payload "
                    f"from {method_name}."
                ),
                source=tool_id,
            )
        ]
