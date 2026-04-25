from __future__ import annotations

from dataclasses import dataclass

from nagient.app.configuration import ProviderInstanceConfig
from nagient.domain.entities.system_state import (
    CheckIssue,
    CredentialRecord,
    ProviderAuthStatus,
    ProviderState,
)
from nagient.providers.base import LoadedProviderPlugin, ProviderPluginManifest


@dataclass(frozen=True)
class ProviderManager:
    def inspect_provider(
        self,
        provider: ProviderInstanceConfig,
        plugin: LoadedProviderPlugin,
        secrets: dict[str, str],
        credential: CredentialRecord | None,
        *,
        is_default: bool = False,
        verify_remote: bool = False,
    ) -> ProviderState:
        manifest = plugin.manifest
        auth_mode = _resolved_auth_mode(provider.config, manifest.default_auth_mode)
        configured_model = _string_config(provider.config.get("model"))
        if not provider.enabled:
            return ProviderState(
                provider_id=provider.provider_id,
                plugin_id=provider.plugin_id,
                enabled=False,
                default=is_default,
                status="disabled",
                authenticated=False,
                auth_mode=auth_mode,
                auth_message="Provider profile is disabled.",
                configured_model=configured_model,
                capabilities=manifest.capabilities,
                issues=[],
            )

        issues: list[CheckIssue] = []
        issues.extend(self._lint_config(provider.provider_id, manifest, provider.config))
        issues.extend(
            self._call_provider_check(
                provider.provider_id,
                plugin,
                "validate_config",
                provider.config,
                secrets,
                credential,
            )
        )
        auth_status = self._read_auth_status(
            provider.provider_id,
            plugin,
            provider.config,
            secrets,
            credential,
            auth_mode,
        )
        issues.extend(auth_status.issues)

        has_structural_error = any(issue.severity == "error" for issue in issues)
        if not has_structural_error and auth_status.authenticated:
            issues.extend(
                self._call_provider_check(
                    provider.provider_id,
                    plugin,
                    "self_test",
                    provider.config,
                    secrets,
                    credential,
                )
            )
            if verify_remote:
                issues.extend(
                    self._call_provider_check(
                        provider.provider_id,
                        plugin,
                        "healthcheck",
                        provider.config,
                        secrets,
                        credential,
                    )
                )

        has_error = any(issue.severity == "error" for issue in issues)
        if has_error:
            status = "failed"
        elif not auth_status.authenticated and auth_mode != "none":
            status = "unauthenticated"
        elif issues:
            status = "degraded"
        else:
            status = "ready"

        return ProviderState(
            provider_id=provider.provider_id,
            plugin_id=provider.plugin_id,
            enabled=True,
            default=is_default,
            status=status,
            authenticated=auth_status.authenticated,
            auth_mode=auth_status.auth_mode,
            auth_message=auth_status.message,
            configured_model=configured_model,
            capabilities=manifest.capabilities,
            issues=issues,
        )

    def _lint_config(
        self,
        provider_id: str,
        manifest: ProviderPluginManifest,
        config: dict[str, object],
    ) -> list[CheckIssue]:
        issues: list[CheckIssue] = []
        for field_name in manifest.required_config:
            if field_name not in config:
                issues.append(
                    CheckIssue(
                        severity="error",
                        code="provider.missing_required_config",
                        message=(
                            f"Provider {provider_id!r} must define required field "
                            f"{field_name!r}."
                        ),
                        source=provider_id,
                    )
                )
        unknown_keys = sorted(set(config) - manifest.allowed_config)
        for key in unknown_keys:
            issues.append(
                CheckIssue(
                    severity="warning",
                    code="provider.unknown_config_key",
                    message=f"Provider {provider_id!r} defines unknown config key {key!r}.",
                    source=provider_id,
                )
            )
        return issues

    def _call_provider_check(
        self,
        provider_id: str,
        plugin: LoadedProviderPlugin,
        method_name: str,
        config: dict[str, object],
        secrets: dict[str, str],
        credential: CredentialRecord | None,
    ) -> list[CheckIssue]:
        method = getattr(plugin.implementation, method_name, None)
        if not callable(method):
            return [
                CheckIssue(
                    severity="error",
                    code="provider.plugin_missing_method",
                    message=(
                        f"Provider plugin {plugin.manifest.plugin_id!r} does not expose "
                        f"method {method_name!r}."
                    ),
                    source=provider_id,
                )
            ]

        try:
            result = method(provider_id, config, secrets, credential)
        except Exception as exc:
            return [
                CheckIssue(
                    severity="error",
                    code="provider.plugin_runtime_error",
                    message=(
                        f"Provider plugin {plugin.manifest.plugin_id!r} raised an "
                        f"exception during {method_name}: {exc}"
                    ),
                    source=provider_id,
                    hint="Inspect the provider plugin code and rerun nagient preflight.",
                )
            ]

        if result is None:
            return []
        if isinstance(result, list) and all(isinstance(item, CheckIssue) for item in result):
            return result
        return [
            CheckIssue(
                severity="error",
                code="provider.plugin_invalid_check_result",
                message=(
                    f"Provider plugin {plugin.manifest.plugin_id!r} returned an invalid "
                    f"result from {method_name}."
                ),
                source=provider_id,
            )
        ]

    def _read_auth_status(
        self,
        provider_id: str,
        plugin: LoadedProviderPlugin,
        config: dict[str, object],
        secrets: dict[str, str],
        credential: CredentialRecord | None,
        default_auth_mode: str,
    ) -> ProviderAuthStatus:
        method = getattr(plugin.implementation, "auth_status", None)
        if not callable(method):
            return ProviderAuthStatus(
                authenticated=False,
                auth_mode=default_auth_mode,
                status="unsupported",
                message="The provider plugin does not expose auth_status().",
                issues=[
                    CheckIssue(
                        severity="error",
                        code="provider.plugin_missing_auth_status",
                        message=(
                            f"Provider plugin {plugin.manifest.plugin_id!r} does not "
                            "expose auth_status()."
                        ),
                        source=provider_id,
                    )
                ],
            )

        try:
            result = method(provider_id, config, secrets, credential)
        except Exception as exc:
            return ProviderAuthStatus(
                authenticated=False,
                auth_mode=default_auth_mode,
                status="failed",
                message=f"Provider auth status failed: {exc}",
                issues=[
                    CheckIssue(
                        severity="error",
                        code="provider.auth_status_failed",
                        message=(
                            f"Provider plugin {plugin.manifest.plugin_id!r} raised an "
                            f"exception during auth_status: {exc}"
                        ),
                        source=provider_id,
                    )
                ],
            )

        if isinstance(result, ProviderAuthStatus):
            return result
        return ProviderAuthStatus(
            authenticated=False,
            auth_mode=default_auth_mode,
            status="invalid",
            message="Provider auth status returned an invalid payload.",
            issues=[
                CheckIssue(
                    severity="error",
                    code="provider.invalid_auth_status",
                    message=(
                        f"Provider plugin {plugin.manifest.plugin_id!r} returned an "
                        "invalid auth_status payload."
                    ),
                    source=provider_id,
                )
            ],
        )


def _resolved_auth_mode(config: dict[str, object], default_auth_mode: str) -> str:
    value = config.get("auth")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default_auth_mode


def _string_config(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None

