from __future__ import annotations

from dataclasses import dataclass

from nagient.app.configuration import load_runtime_configuration
from nagient.app.settings import Settings
from nagient.domain.entities.system_state import (
    ActivationReport,
    CheckIssue,
    ProviderState,
    TransportState,
)
from nagient.plugins.manager import TransportManager
from nagient.plugins.registry import TransportPluginRegistry
from nagient.providers.manager import ProviderManager
from nagient.providers.registry import ProviderPluginRegistry
from nagient.providers.storage import FileCredentialStore


@dataclass(frozen=True)
class PreflightService:
    settings: Settings
    plugin_registry: TransportPluginRegistry
    transport_manager: TransportManager
    provider_registry: ProviderPluginRegistry
    provider_manager: ProviderManager
    credential_store: FileCredentialStore

    def inspect(self) -> ActivationReport:
        runtime_config = load_runtime_configuration(self.settings)
        discovery = self.plugin_registry.discover(self.settings.plugins_dir)
        provider_discovery = self.provider_registry.discover(self.settings.providers_dir)
        issues = list(discovery.issues)
        issues.extend(provider_discovery.issues)
        transports: list[TransportState] = []
        providers: list[ProviderState] = []
        healthy_transports = 0
        enabled_transports = 0
        ready_providers = 0
        enabled_providers = 0

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

        for provider in runtime_config.providers:
            plugin = provider_discovery.plugins.get(provider.plugin_id)
            if plugin is None:
                severity = "error" if provider.enabled else "warning"
                issue = CheckIssue(
                    severity=severity,
                    code="provider.plugin_not_found",
                    message=(
                        f"Provider {provider.provider_id!r} references unknown plugin "
                        f"{provider.plugin_id!r}."
                    ),
                    source=provider.provider_id,
                )
                issues.append(issue)
                providers.append(
                    ProviderState(
                        provider_id=provider.provider_id,
                        plugin_id=provider.plugin_id,
                        enabled=provider.enabled,
                        default=runtime_config.default_provider == provider.provider_id,
                        status="failed" if provider.enabled else "disabled",
                        authenticated=False,
                        auth_mode=str(provider.config.get("auth", "unknown")),
                        auth_message=issue.message,
                        configured_model=(
                            str(provider.config.get("model"))
                            if isinstance(provider.config.get("model"), str)
                            else None
                        ),
                        capabilities=[],
                        issues=[issue],
                    )
                )
                if provider.enabled:
                    enabled_providers += 1
                continue

            credential = self.credential_store.load(provider.provider_id)
            state = self.provider_manager.inspect_provider(
                provider=provider,
                plugin=plugin,
                secrets=runtime_config.secrets,
                credential=credential,
                is_default=runtime_config.default_provider == provider.provider_id,
            )
            providers.append(state)
            issues.extend(state.issues)
            if provider.enabled:
                enabled_providers += 1
                if state.status in {"ready", "degraded"} and state.authenticated:
                    ready_providers += 1

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

        issues.extend(
            self._evaluate_provider_runtime(
                runtime_config.default_provider,
                runtime_config.require_provider,
                enabled_providers,
                ready_providers,
                providers,
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
            providers=providers,
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

    def _evaluate_provider_runtime(
        self,
        default_provider: str | None,
        require_provider: bool,
        enabled_providers: int,
        ready_providers: int,
        providers: list[ProviderState],
    ) -> list[CheckIssue]:
        issues: list[CheckIssue] = []
        if enabled_providers == 0:
            if not require_provider and default_provider is None:
                return issues
            severity = "error" if require_provider else "warning"
            issues.append(
                CheckIssue(
                    severity=severity,
                    code="runtime.no_enabled_providers",
                    message="No providers are enabled.",
                    source="runtime",
                    hint="Enable at least one provider profile in config.toml.",
                )
            )
            return issues

        if ready_providers == 0:
            severity = "error" if require_provider else "warning"
            issues.append(
                CheckIssue(
                    severity=severity,
                    code="runtime.no_ready_providers",
                    message="No enabled providers are authenticated and ready.",
                    source="runtime",
                    hint=(
                        "Run nagient auth status and nagient auth login after fixing "
                        "provider config."
                    ),
                )
            )

        if default_provider is None:
            issues.append(
                CheckIssue(
                    severity="warning",
                    code="runtime.default_provider_not_set",
                    message="No default provider profile is configured.",
                    source="runtime",
                    hint="Set [agent].default_provider to the profile your agent should use.",
                )
            )
            return issues

        provider_state = next(
            (provider for provider in providers if provider.provider_id == default_provider),
            None,
        )
        if provider_state is None:
            issues.append(
                CheckIssue(
                    severity="error",
                    code="runtime.default_provider_not_found",
                    message=f"Default provider {default_provider!r} was not found.",
                    source="runtime",
                )
            )
            return issues

        if provider_state.status not in {"ready", "degraded"}:
            issues.append(
                CheckIssue(
                    severity="error",
                    code="runtime.default_provider_not_ready",
                    message=(
                        f"Default provider {default_provider!r} is not ready; current "
                        f"status is {provider_state.status!r}."
                    ),
                    source=default_provider,
                    hint="Run nagient auth status and nagient auth login to repair the profile.",
                )
            )
        return issues
