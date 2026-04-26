from __future__ import annotations

from dataclasses import dataclass

from nagient.app.configuration import load_runtime_configuration
from nagient.app.settings import Settings
from nagient.application.services.agent_turn_service import AgentTurnService
from nagient.application.services.configuration_service import ConfigurationService
from nagient.application.services.health_service import HealthService
from nagient.application.services.preflight_service import PreflightService
from nagient.application.services.provider_service import ProviderService
from nagient.application.services.reconcile_service import ReconcileService
from nagient.application.services.status_service import StatusService
from nagient.application.services.tool_service import ToolService
from nagient.application.services.update_service import UpdateService
from nagient.application.services.workflow_service import WorkflowService
from nagient.backups.manager import BackupManager
from nagient.infrastructure.registry import ManifestRegistry
from nagient.infrastructure.runtime import RuntimeAgent
from nagient.plugins.manager import TransportManager
from nagient.plugins.registry import TransportPluginRegistry
from nagient.providers.manager import ProviderManager
from nagient.providers.registry import ProviderPluginRegistry
from nagient.providers.storage import AuthSessionStore, FileCredentialStore
from nagient.security.broker import SecretBroker
from nagient.security.workflows import WorkflowStore
from nagient.tools.manager import ToolManager
from nagient.tools.registry import ToolPluginRegistry
from nagient.workspace.manager import WorkspaceManager


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
    tool_registry: ToolPluginRegistry
    tool_manager: ToolManager
    secret_broker: SecretBroker
    workspace_manager: WorkspaceManager
    backup_manager: BackupManager
    workflow_store: WorkflowStore
    workflow_service: WorkflowService
    tool_service: ToolService
    provider_service: ProviderService
    preflight_service: PreflightService
    reconcile_service: ReconcileService
    agent_turn_service: AgentTurnService
    runtime_agent: RuntimeAgent


def build_container(settings: Settings | None = None) -> AppContainer:
    resolved_settings = settings or Settings.from_env()
    registry = ManifestRegistry(resolved_settings.update_base_url)
    update_service = UpdateService(registry=registry)
    plugin_registry = TransportPluginRegistry()
    transport_manager = TransportManager()
    provider_registry = ProviderPluginRegistry()
    provider_manager = ProviderManager()
    tool_registry = ToolPluginRegistry()
    tool_manager = ToolManager()
    secret_broker = SecretBroker(resolved_settings)
    workspace_manager = WorkspaceManager(resolved_settings)
    backup_manager = BackupManager()
    workflow_store = WorkflowStore(resolved_settings)
    credential_store = FileCredentialStore(resolved_settings.credentials_dir)
    auth_session_store = AuthSessionStore(resolved_settings.state_dir / "auth-sessions")
    workflow_service = WorkflowService(
        settings=resolved_settings,
        workflow_store=workflow_store,
        secret_broker=secret_broker,
        backup_restorer=lambda snapshot_id: _restore_workspace_snapshot(
            resolved_settings,
            workspace_manager,
            backup_manager,
            snapshot_id,
        ),
        reconcile_runner=lambda: {"status": "pending"},
        assistant_resume_handler=lambda response: {
            "status": "queued",
            "assistant_response": response.to_dict(),
        },
    )
    tool_service = ToolService(
        settings=resolved_settings,
        tool_registry=tool_registry,
        tool_manager=tool_manager,
        secret_broker=secret_broker,
        workspace_manager=workspace_manager,
        backup_manager=backup_manager,
        workflow_service=workflow_service,
    )
    provider_service = ProviderService(
        settings=resolved_settings,
        provider_registry=provider_registry,
        provider_manager=provider_manager,
        credential_store=credential_store,
        auth_session_store=auth_session_store,
        secret_broker=secret_broker,
    )
    preflight_service = PreflightService(
        settings=resolved_settings,
        plugin_registry=plugin_registry,
        transport_manager=transport_manager,
        provider_registry=provider_registry,
        provider_manager=provider_manager,
        credential_store=credential_store,
        tool_registry=tool_registry,
        tool_manager=tool_manager,
        secret_broker=secret_broker,
        workspace_manager=workspace_manager,
    )
    reconcile_service = ReconcileService(
        settings=resolved_settings,
        preflight_service=preflight_service,
        workspace_manager=workspace_manager,
    )
    tool_service.reconcile_runner = lambda: reconcile_service.reconcile().to_dict()
    workflow_service.reconcile_runner = lambda: reconcile_service.reconcile().to_dict()
    workflow_service.tool_invoker = lambda payload: tool_service.invoke_from_dict(payload)
    agent_turn_service = AgentTurnService(
        tool_service=tool_service,
        workflow_service=workflow_service,
    )
    return AppContainer(
        settings=resolved_settings,
        registry=registry,
        health_service=HealthService(resolved_settings),
        status_service=StatusService(
            settings=resolved_settings,
            update_service=update_service,
            secret_broker=secret_broker,
            workflow_store=workflow_store,
            workspace_manager=workspace_manager,
        ),
        update_service=update_service,
        configuration_service=ConfigurationService(
            resolved_settings,
            transport_registry=plugin_registry,
            provider_registry=provider_registry,
            tool_registry=tool_registry,
            provider_service=provider_service,
        ),
        plugin_registry=plugin_registry,
        transport_manager=transport_manager,
        provider_registry=provider_registry,
        provider_manager=provider_manager,
        tool_registry=tool_registry,
        tool_manager=tool_manager,
        secret_broker=secret_broker,
        workspace_manager=workspace_manager,
        backup_manager=backup_manager,
        workflow_store=workflow_store,
        workflow_service=workflow_service,
        tool_service=tool_service,
        provider_service=provider_service,
        preflight_service=preflight_service,
        reconcile_service=reconcile_service,
        agent_turn_service=agent_turn_service,
        runtime_agent=RuntimeAgent(
            settings=resolved_settings,
            activation_runner=reconcile_service.reconcile,
            plugin_registry=plugin_registry,
        ),
    )


def _restore_workspace_snapshot(
    settings: Settings,
    workspace_manager: WorkspaceManager,
    backup_manager: BackupManager,
    snapshot_id: str,
) -> dict[str, object]:
    runtime_config = load_runtime_configuration(settings)
    layout = workspace_manager.ensure_layout(runtime_config.workspace)
    return backup_manager.restore_snapshot(layout, snapshot_id)
