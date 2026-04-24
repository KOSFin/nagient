from __future__ import annotations

from collections.abc import Iterable

from nagient.domain.entities.release import MigrationStep
from nagient.domain.versioning import Version


def plan_migrations(
    current_version: Version,
    target_version: Version,
    candidates: Iterable[MigrationStep],
) -> list[MigrationStep]:
    planned: list[MigrationStep] = []
    cursor = current_version

    for step in sorted(candidates, key=lambda item: (item.from_version, item.to_version)):
        if step.from_version == cursor and step.to_version <= target_version:
            planned.append(step)
            cursor = step.to_version

    return planned

