from __future__ import annotations

from dataclasses import dataclass, field

from nagient.domain.versioning import Version


@dataclass(frozen=True)
class ReleaseArtifact:
    name: str
    url: str
    kind: str
    platform: str = "any"


@dataclass(frozen=True)
class MigrationStep:
    step_id: str
    from_version: Version
    to_version: Version
    description: str
    command: str


@dataclass(frozen=True)
class ReleaseManifest:
    version: Version
    channel: str
    published_at: str
    summary: str
    docker_image: str
    compose_url: str | None = None
    artifacts: list[ReleaseArtifact] = field(default_factory=list)
    migrations: list[MigrationStep] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)

