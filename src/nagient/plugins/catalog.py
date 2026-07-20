"""Small, reviewed catalog of plugins shipped or maintained by Nagient.

The catalog is intentionally data-only. External repositories can be added to the
JSON metadata without changing the installer, while the CLI keeps a clear
distinction between ``official`` and merely discovered code on disk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CatalogEntry:
    plugin_id: str
    family: str
    display_name: str
    description: str
    source: str
    version: str
    verified: bool = True
    bundled: bool = False
    ref: str | None = None
    docs: str = ""
    env: tuple[str, ...] = ()

    def to_dict(self, *, installed: bool = False) -> dict[str, object]:
        return {
            "plugin_id": self.plugin_id,
            "family": self.family,
            "display_name": self.display_name,
            "description": self.description,
            "source": self.source,
            "version": self.version,
            "verified": self.verified,
            "bundled": self.bundled,
            "ref": self.ref,
            "installed": installed,
            "docs": self.docs,
            "env": list(self.env),
        }


# Keep this fallback in the wheel. The matching metadata file is published for
# GitHub Pages and can grow independently as external plugin repositories appear.
OFFICIAL_CATALOG: tuple[CatalogEntry, ...] = (
    CatalogEntry(
        plugin_id="builtin.console",
        family="transport",
        display_name="Console Transport",
        description="Local terminal transport; enabled by default for first-run setup.",
        source="builtin",
        version="0.1.0",
        bundled=True,
        docs="docs/commands.md#chat",
    ),
    CatalogEntry(
        plugin_id="builtin.telegram",
        family="transport",
        display_name="Telegram Transport",
        description="Telegram Bot API polling, replies, callbacks, and chat allowlists.",
        source="builtin",
        version="0.1.0",
        bundled=True,
        docs="docs/plugins.md#telegram",
        env=("NAGIENT_TRANSPORT__TELEGRAM__BOT_TOKEN_SECRET", "TELEGRAM_BOT_TOKEN"),
    ),
    CatalogEntry(
        plugin_id="builtin.webhook",
        family="transport",
        display_name="Webhook Transport",
        description="HTTP webhook ingress for service-to-service integrations.",
        source="builtin",
        version="0.1.0",
        bundled=True,
        docs="docs/plugin-contracts.md",
    ),
    CatalogEntry(
        plugin_id="github.api",
        family="tool",
        display_name="GitHub API",
        description="Scoped GitHub issue, pull request, repository, and release operations.",
        source="builtin",
        version="0.1.0",
        bundled=True,
        docs="docs/plugins.md#github-api",
        env=("NAGIENT_TOOL__GITHUB_API__TOKEN_SECRET", "GITHUB_TOKEN"),
    ),
    CatalogEntry(
        plugin_id="nagient.telegram",
        family="transport",
        display_name="Nagient Telegram Transport",
        description=(
            "Separately versioned Telegram transport repository with allowlists "
            "and streaming edits."
        ),
        source="https://github.com/KOSFin/nagient-transport-telegram.git",
        version="0.1.0",
        ref="v0.1.0",
        docs="https://github.com/KOSFin/nagient-transport-telegram#readme",
        env=("NAGIENT_TRANSPORT__TELEGRAM__BOT_TOKEN_SECRET", "TELEGRAM_BOT_TOKEN"),
    ),
    CatalogEntry(
        plugin_id="nagient.github_api",
        family="tool",
        display_name="Nagient GitHub API",
        description="Separately versioned GitHub API tool with approval-gated writes.",
        source="https://github.com/KOSFin/nagient-tool-github-api.git",
        version="0.1.0",
        ref="v0.1.0",
        docs="https://github.com/KOSFin/nagient-tool-github-api#readme",
        env=("NAGIENT_TOOL__GITHUB_API__TOKEN_SECRET", "GITHUB_TOKEN"),
    ),
)


def catalog_entries(
    *, family: str | None = None, verified_only: bool = False
) -> list[CatalogEntry]:
    catalog = _read_metadata_catalog() or OFFICIAL_CATALOG
    return [
        entry
        for entry in catalog
        if (family is None or entry.family == family)
        and (not verified_only or entry.verified)
    ]


def catalog_payload(
    *,
    family: str | None = None,
    verified_only: bool = False,
    installed_ids: set[str] | None = None,
) -> dict[str, object]:
    installed = installed_ids or set()
    entries = [
        entry.to_dict(installed=entry.plugin_id in installed)
        for entry in catalog_entries(family=family, verified_only=verified_only)
    ]
    return {
        "catalog": "official",
        "verified_only": verified_only,
        "count": len(entries),
        "plugins": entries,
    }


def catalog_entry(plugin_id: str) -> CatalogEntry | None:
    normalized = plugin_id.strip().lower()
    catalog = _read_metadata_catalog() or OFFICIAL_CATALOG
    return next(
        (entry for entry in catalog if entry.plugin_id.lower() == normalized),
        None,
    )


def _read_metadata_catalog() -> list[CatalogEntry]:
    """Use the published JSON catalog when running from a source checkout."""
    path = Path(__file__).resolve().parents[3] / "metadata" / "plugins" / "catalog.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return catalog_from_json(payload)


def catalog_from_json(payload: Any) -> list[CatalogEntry]:
    """Parse a future remote catalog while rejecting malformed entries."""
    if not isinstance(payload, dict) or not isinstance(payload.get("plugins"), list):
        return []
    result: list[CatalogEntry] = []
    for raw in payload["plugins"]:
        if not isinstance(raw, dict):
            continue
        required = [
            raw.get(key)
            for key in ("plugin_id", "family", "display_name", "source", "version")
        ]
        if not all(isinstance(value, str) and value.strip() for value in required):
            continue
        if raw["family"] not in {"transport", "provider", "tool"}:
            continue
        result.append(
            CatalogEntry(
                plugin_id=str(raw["plugin_id"]),
                family=str(raw["family"]),
                display_name=str(raw["display_name"]),
                description=str(raw.get("description", "")),
                source=str(raw["source"]),
                version=str(raw["version"]),
                verified=bool(raw.get("verified", False)),
                bundled=bool(raw.get("bundled", False)),
                ref=str(raw["ref"]) if isinstance(raw.get("ref"), str) else None,
                docs=str(raw.get("docs", "")),
                env=tuple(str(item) for item in raw.get("env", []) if isinstance(item, str)),
            )
        )
    return result
