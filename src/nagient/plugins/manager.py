from __future__ import annotations

from dataclasses import dataclass

from nagient.app.configuration import TransportInstanceConfig
from nagient.domain.entities.system_state import CheckIssue, TransportState
from nagient.plugins.base import LoadedTransportPlugin


@dataclass(frozen=True)
class TransportManager:
    def inspect_transport(
        self,
        transport: TransportInstanceConfig,
        plugin: LoadedTransportPlugin,
        secrets: dict[str, str],
    ) -> TransportState:
        issues: list[CheckIssue] = []
        manifest = plugin.manifest
        if not transport.enabled:
            return TransportState(
                transport_id=transport.transport_id,
                plugin_id=transport.plugin_id,
                enabled=False,
                status="disabled",
                exposed_functions=manifest.exposed_functions,
                issues=[],
            )

        issues.extend(self._lint_config(transport.transport_id, manifest, transport.config))
        issues.extend(
            self._call_plugin_check(
                transport.transport_id,
                plugin,
                "validate_config",
                transport.config,
                secrets,
            )
        )
        if not any(issue.severity == "error" for issue in issues):
            issues.extend(
                self._call_plugin_check(
                    transport.transport_id,
                    plugin,
                    "self_test",
                    transport.config,
                    secrets,
                )
            )
            issues.extend(
                self._call_plugin_check(
                    transport.transport_id,
                    plugin,
                    "healthcheck",
                    transport.config,
                    secrets,
                )
            )

        status = "ready"
        if any(issue.severity == "error" for issue in issues):
            status = "failed"
        elif issues:
            status = "degraded"

        return TransportState(
            transport_id=transport.transport_id,
            plugin_id=transport.plugin_id,
            enabled=True,
            status=status,
            exposed_functions=manifest.exposed_functions,
            issues=issues,
        )

    def _lint_config(
        self,
        transport_id: str,
        manifest: LoadedTransportPlugin | object,
        config: dict[str, object],
    ) -> list[CheckIssue]:
        actual_manifest = (
            manifest.manifest if isinstance(manifest, LoadedTransportPlugin) else manifest
        )
        issues: list[CheckIssue] = []
        for field_name in actual_manifest.required_config:
            if field_name not in config:
                issues.append(
                    CheckIssue(
                        severity="error",
                        code="transport.missing_required_config",
                        message=(
                            f"Transport {transport_id!r} must define required field "
                            f"{field_name!r}."
                        ),
                        source=transport_id,
                    )
                )

        unknown_keys = sorted(set(config) - actual_manifest.allowed_config)
        for key in unknown_keys:
            issues.append(
                CheckIssue(
                    severity="warning",
                    code="transport.unknown_config_key",
                    message=f"Transport {transport_id!r} defines unknown config key {key!r}.",
                    source=transport_id,
                )
            )

        return issues

    def _call_plugin_check(
        self,
        transport_id: str,
        plugin: LoadedTransportPlugin,
        method_name: str,
        config: dict[str, object],
        secrets: dict[str, str],
    ) -> list[CheckIssue]:
        method = getattr(plugin.implementation, method_name, None)
        if not callable(method):
            return [
                CheckIssue(
                    severity="error",
                    code="transport.plugin_missing_method",
                    message=(
                        f"Plugin {plugin.manifest.plugin_id!r} does not expose method "
                        f"{method_name!r}."
                    ),
                    source=transport_id,
                )
            ]

        try:
            result = method(transport_id, config, secrets)
        except Exception as exc:
            return [
                CheckIssue(
                    severity="error",
                    code="transport.plugin_runtime_error",
                    message=(
                        f"Plugin {plugin.manifest.plugin_id!r} raised an exception during "
                        f"{method_name}: {exc}"
                    ),
                    source=transport_id,
                    hint="Inspect the plugin code and rerun nagient preflight.",
                )
            ]

        if result is None:
            return []
        if isinstance(result, list) and all(isinstance(item, CheckIssue) for item in result):
            return result
        return [
            CheckIssue(
                severity="error",
                code="transport.plugin_invalid_check_result",
                message=(
                    f"Plugin {plugin.manifest.plugin_id!r} returned an invalid result from "
                    f"{method_name}."
                ),
                source=transport_id,
            )
        ]
