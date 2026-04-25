from __future__ import annotations

from dataclasses import dataclass

from nagient.app.settings import Settings
from nagient.application.services.configuration_service import ConfigurationService
from nagient.application.services.health_service import HealthService
from nagient.application.services.preflight_service import PreflightService
from nagient.application.services.provider_service import ProviderService
from nagient.application.services.reconcile_service import ReconcileService
from nagient.application.services.status_service import StatusService
from nagient.application.services.update_service import UpdateService
from nagient.infrastructure.registry import ManifestRegistry
from nagient.infrastructure.runtime import RuntimeAgent
from nagient.plugins.manager import TransportManager
from nagient.plugins.registry import TransportPluginRegistry
from nagient.providers.manager import ProviderManager
from nagient.providers.registry import ProviderPluginRegistry
from nagient.providers.storage import AuthSessionStore, FileCredentialStore


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
    provider_registry: ProviderPluginRegistry
    provider_manager: ProviderManager
    provider_service: ProviderService
    preflight_service: PreflightService
    reconcile_service: ReconcileService
    runtime_agent: RuntimeAgent


def build_container(settings: Settings | None = None) -> AppContainer:
    resolved_settings = settings or Settings.from_env()
    registry = ManifestRegistry(resolved_settings.update_base_url)
    update_service = UpdateService(registry=registry)
    plugin_registry = TransportPluginRegistry()
    transport_manager = TransportManager()
    provider_registry = ProviderPluginRegistry()
    provider_manager = ProviderManager()
    credential_store = FileCredentialStore(resolved_settings.credentials_dir)
    auth_session_store = AuthSessionStore(resolved_settings.state_dir / "auth-sessions")
    preflight_service = PreflightService(
        settings=resolved_settings,
        plugin_registry=plugin_registry,
        transport_manager=transport_manager,
        provider_registry=provider_registry,
        provider_manager=provider_manager,
        credential_store=credential_store,
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
        provider_registry=provider_registry,
        provider_manager=provider_manager,
        provider_service=ProviderService(
            settings=resolved_settings,
            provider_registry=provider_registry,
            provider_manager=provider_manager,
            credential_store=credential_store,
            auth_session_store=auth_session_store,
        ),
        preflight_service=preflight_service,
        reconcile_service=reconcile_service,
        runtime_agent=RuntimeAgent(
            settings=resolved_settings,
            activation_runner=reconcile_service.reconcile,
        ),
    )
