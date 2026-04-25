from __future__ import annotations

from dataclasses import dataclass

from nagient.app.settings import Settings
from nagient.application.services.configuration_service import ConfigurationService
from nagient.application.services.health_service import HealthService
from nagient.application.services.preflight_service import PreflightService
from nagient.application.services.reconcile_service import ReconcileService
from nagient.application.services.status_service import StatusService
from nagient.application.services.update_service import UpdateService
from nagient.infrastructure.registry import ManifestRegistry
from nagient.infrastructure.runtime import RuntimeAgent
from nagient.plugins.manager import TransportManager
from nagient.plugins.registry import TransportPluginRegistry


@dataclass(frozen=True)
class AppContainer:
    settings: Settings
    registry: ManifestRegistry
    health_service: HealthService
    status_service: StatusService
    update_service: UpdateService
    configuration_service: ConfigurationService
    plugin_registry: TransportPluginRegistry
    transport_manager: TransportManager
    preflight_service: PreflightService
    reconcile_service: ReconcileService
    runtime_agent: RuntimeAgent


def build_container(settings: Settings | None = None) -> AppContainer:
    resolved_settings = settings or Settings.from_env()
    registry = ManifestRegistry(resolved_settings.update_base_url)
    update_service = UpdateService(registry=registry)
    plugin_registry = TransportPluginRegistry()
    transport_manager = TransportManager()
    preflight_service = PreflightService(
        settings=resolved_settings,
        plugin_registry=plugin_registry,
        transport_manager=transport_manager,
    )
    reconcile_service = ReconcileService(
        settings=resolved_settings,
        preflight_service=preflight_service,
    )
    return AppContainer(
        settings=resolved_settings,
        registry=registry,
        health_service=HealthService(resolved_settings),
        status_service=StatusService(
            settings=resolved_settings,
            update_service=update_service,
        ),
        update_service=update_service,
        configuration_service=ConfigurationService(resolved_settings),
        plugin_registry=plugin_registry,
        transport_manager=transport_manager,
        preflight_service=preflight_service,
        reconcile_service=reconcile_service,
        runtime_agent=RuntimeAgent(
            settings=resolved_settings,
            activation_runner=reconcile_service.reconcile,
        ),
    )
