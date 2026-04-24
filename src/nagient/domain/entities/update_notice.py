from __future__ import annotations

from dataclasses import dataclass, field

from nagient.domain.entities.release import MigrationStep, ReleaseManifest
from nagient.domain.versioning import Version


@dataclass(frozen=True)
class UpdateNotice:
    current_version: Version
    target_version: Version
    update_available: bool
    message: str
    manifest: ReleaseManifest | None = None
    planned_migrations: list[MigrationStep] = field(default_factory=list)

