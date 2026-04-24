from __future__ import annotations

from dataclasses import dataclass

from nagient.domain.entities.update_notice import UpdateNotice
from nagient.domain.versioning import Version
from nagient.infrastructure.registry import ManifestRegistry
from nagient.migrations.planner import plan_migrations


@dataclass(frozen=True)
class UpdateService:
    registry: ManifestRegistry

    def check(
        self,
        current_version: str,
        channel: str = "stable",
        manifest_ref: str | None = None,
    ) -> UpdateNotice:
        current = Version.parse(current_version)
        manifest = (
            self.registry.load_release_manifest(manifest_ref)
            if manifest_ref
            else self.registry.fetch_latest_release(channel)
        )
        target = manifest.version
        planned = plan_migrations(current, target, manifest.migrations)
        update_available = current < target

        if update_available:
            message = f"Update available: {current} -> {target}"
        else:
            message = f"Already up to date on {current}"

        return UpdateNotice(
            current_version=current,
            target_version=target,
            update_available=update_available,
            message=message,
            manifest=manifest,
            planned_migrations=planned,
        )

