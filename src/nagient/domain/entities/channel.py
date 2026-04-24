from __future__ import annotations

from dataclasses import dataclass, field

from nagient.domain.versioning import Version


@dataclass(frozen=True)
class ChannelManifest:
    channel: str
    latest_version: Version
    manifest_url: str
    published_at: str
    supported_installers: list[str] = field(default_factory=list)

