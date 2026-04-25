from __future__ import annotations

from dataclasses import dataclass

from nagient.app.configuration import load_runtime_configuration
from nagient.app.settings import Settings
from nagient.domain.entities.system_state import ActivationReport, CheckIssue, TransportState
from nagient.plugins.manager import TransportManager
from nagient.plugins.registry import TransportPluginRegistry


@dataclass(frozen=True)
class PreflightService:
    settings: Settings
    plugin_registry: TransportPluginRegistry
    transport_manager: TransportManager

    def inspect(self) -> ActivationReport:
        runtime_config = load_runtime_configuration(self.settings)
        discovery = self.plugin_registry.discover(self.settings.plugins_dir)
        issues = list(discovery.issues)
        transports: list[TransportState] = []
        healthy_transports = 0
        enabled_transports = 0

        for transport in runtime_config.transports:
            plugin = discovery.plugins.get(transport.plugin_id)
            if plugin is None:
                severity = "error" if transport.enabled else "warning"
                issue = CheckIssue(
                    severity=severity,
                    code="transport.plugin_not_found",
                    message=(
                        f"Transport {transport.transport_id!r} references unknown plugin "
                        f"{transport.plugin_id!r}."
                    ),
                    source=transport.transport_id,
                )
                issues.append(issue)
                transports.append(
                    TransportState(
                        transport_id=transport.transport_id,
                        plugin_id=transport.plugin_id,
                        enabled=transport.enabled,
                        status="failed" if transport.enabled else "disabled",
                        exposed_functions=[],
                        issues=[issue],
                    )
                )
                if transport.enabled:
                    enabled_transports += 1
                continue

            state = self.transport_manager.inspect_transport(
                transport=transport,
                plugin=plugin,
                secrets=runtime_config.secrets,
            )
            transports.append(state)
            issues.extend(state.issues)
            if transport.enabled:
                enabled_transports += 1
                if state.status == "ready":
                    healthy_transports += 1

        if enabled_transports == 0:
            issues.append(
                CheckIssue(
                    severity="error" if runtime_config.safe_mode else "warning",
                    code="runtime.no_enabled_transports",
                    message="No transports are enabled.",
                    source="runtime",
                    hint="Enable at least one transport in config.toml.",
                )
            )

        if enabled_transports > 0 and healthy_transports == 0:
            issues.append(
                CheckIssue(
                    severity="error" if runtime_config.safe_mode else "warning",
                    code="runtime.no_healthy_transports",
                    message="No enabled transports passed validation and self-tests.",
                    source="runtime",
                    hint="Run nagient preflight after fixing secrets or transport settings.",
                )
            )

        errors = [issue for issue in issues if issue.severity == "error"]
        warnings = [issue for issue in issues if issue.severity == "warning"]
        can_activate = not runtime_config.safe_mode or not errors
        if not can_activate:
            status = "blocked"
        elif errors or warnings:
            status = "degraded"
        else:
            status = "ready"

        return ActivationReport(
            status=status,
            safe_mode=runtime_config.safe_mode,
            can_activate=can_activate,
            transports=transports,
            issues=issues,
            notices=self._build_notices(status, issues),
            effective_config=runtime_config.to_dict(),
        )

    def _build_notices(self, status: str, issues: list[CheckIssue]) -> list[str]:
        notices = [f"Runtime activation status: {status}."]
        for issue in issues:
            if issue.severity == "error":
                notices.append(f"{issue.source}: {issue.message}")
        return notices
