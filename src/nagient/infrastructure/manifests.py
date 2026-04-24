from __future__ import annotations

from nagient.domain.entities.channel import ChannelManifest
from nagient.domain.entities.release import MigrationStep, ReleaseArtifact, ReleaseManifest
from nagient.domain.versioning import Version


def parse_channel_manifest(payload: dict[str, object]) -> ChannelManifest:
    return ChannelManifest(
        channel=_require_string(payload, "channel"),
        latest_version=Version.parse(_require_string(payload, "latest_version")),
        manifest_url=_require_string(payload, "manifest_url"),
        published_at=_require_string(payload, "published_at"),
        supported_installers=_string_list(payload.get("supported_installers")),
    )


def parse_release_manifest(payload: dict[str, object]) -> ReleaseManifest:
    docker = _require_dict(payload, "docker")
    return ReleaseManifest(
        version=Version.parse(_require_string(payload, "version")),
        channel=_require_string(payload, "channel"),
        published_at=_require_string(payload, "published_at"),
        summary=_require_string(payload, "summary"),
        docker_image=_require_string(docker, "image"),
        compose_url=_optional_string(docker.get("compose_url")),
        artifacts=[
            ReleaseArtifact(
                name=_require_string(item, "name"),
                url=_require_string(item, "url"),
                kind=_require_string(item, "kind"),
                platform=_optional_string(item.get("platform")) or "any",
            )
            for item in _dict_list(payload.get("artifacts"))
        ],
        migrations=[
            MigrationStep(
                step_id=_require_string(item, "id"),
                from_version=Version.parse(_require_string(item, "from_version")),
                to_version=Version.parse(_require_string(item, "to_version")),
                description=_require_string(item, "description"),
                command=_require_string(item, "command"),
            )
            for item in _dict_list(payload.get("migrations"))
        ],
        notices=_string_list(payload.get("notices")),
    )


def channel_to_dict(channel: ChannelManifest) -> dict[str, object]:
    return {
        "channel": channel.channel,
        "latest_version": str(channel.latest_version),
        "manifest_url": channel.manifest_url,
        "published_at": channel.published_at,
        "supported_installers": channel.supported_installers,
    }


def release_to_dict(manifest: ReleaseManifest) -> dict[str, object]:
    return {
        "version": str(manifest.version),
        "channel": manifest.channel,
        "published_at": manifest.published_at,
        "summary": manifest.summary,
        "docker": {
            "image": manifest.docker_image,
            "compose_url": manifest.compose_url,
        },
        "artifacts": [
            {
                "name": artifact.name,
                "url": artifact.url,
                "kind": artifact.kind,
                "platform": artifact.platform,
            }
            for artifact in manifest.artifacts
        ],
        "migrations": [
            {
                "id": migration.step_id,
                "from_version": str(migration.from_version),
                "to_version": str(migration.to_version),
                "description": migration.description,
                "command": migration.command,
            }
            for migration in manifest.migrations
        ],
        "notices": manifest.notices,
    }


def _require_dict(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        msg = f"Manifest field {key!r} must be an object."
        raise ValueError(msg)
    return value


def _require_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        msg = f"Manifest field {key!r} must be a non-empty string."
        raise ValueError(msg)
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        msg = "Expected string or null."
        raise ValueError(msg)
    return value


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        msg = "Expected a list of strings."
        raise ValueError(msg)
    return list(value)


def _dict_list(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        msg = "Expected a list of objects."
        raise ValueError(msg)
    return [dict(item) for item in value]

