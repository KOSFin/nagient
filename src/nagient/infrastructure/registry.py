from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen

from nagient.domain.entities.channel import ChannelManifest
from nagient.domain.entities.release import ReleaseManifest
from nagient.infrastructure.manifests import (
    parse_channel_manifest,
    parse_release_manifest,
)


def _is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"}


@dataclass(frozen=True)
class ManifestRegistry:
    base_ref: str

    def load_channel(self, channel: str) -> ChannelManifest:
        channel_ref = self._compose_ref(f"channels/{channel}.json")
        payload = self._load_json(channel_ref)
        return parse_channel_manifest(payload)

    def load_release_manifest(self, ref: str) -> ReleaseManifest:
        resolved_ref = ref
        if not _is_url(ref) and not Path(ref).is_absolute():
            resolved_ref = self._compose_ref(ref)
        payload = self._load_json(resolved_ref)
        return parse_release_manifest(payload)

    def fetch_latest_release(self, channel: str) -> ReleaseManifest:
        channel_manifest = self.load_channel(channel)
        return self.load_release_manifest(channel_manifest.manifest_url)

    def _compose_ref(self, suffix: str) -> str:
        if _is_url(self.base_ref):
            return urljoin(self.base_ref.rstrip("/") + "/", suffix)
        return str(Path(self.base_ref) / suffix)

    def _load_json(self, ref: str) -> dict[str, object]:
        if _is_url(ref):
            with urlopen(ref, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        else:
            payload = json.loads(Path(ref).read_text(encoding="utf-8"))

        if not isinstance(payload, dict):
            msg = f"Expected JSON object at {ref!r}."
            raise ValueError(msg)

        return {str(key): value for key, value in payload.items()}
