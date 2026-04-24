from __future__ import annotations

from dataclasses import dataclass

from nagient.app.settings import Settings
from nagient.application.services.health_service import HealthService
from nagient.application.services.update_service import UpdateService
from nagient.infrastructure.registry import ManifestRegistry
from nagient.infrastructure.runtime import RuntimeAgent


@dataclass(frozen=True)
class AppContainer:
    settings: Settings
    registry: ManifestRegistry
    health_service: HealthService
    update_service: UpdateService
    runtime_agent: RuntimeAgent


def build_container(settings: Settings | None = None) -> AppContainer:
    resolved_settings = settings or Settings.from_env()
    registry = ManifestRegistry(resolved_settings.update_base_url)
    return AppContainer(
        settings=resolved_settings,
        registry=registry,
        health_service=HealthService(resolved_settings),
        update_service=UpdateService(registry=registry),
        runtime_agent=RuntimeAgent(settings=resolved_settings),
    )

