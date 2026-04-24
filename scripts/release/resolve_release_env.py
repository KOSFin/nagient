#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from nagient.version import __version__  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve centralized release metadata for Nagient."
    )
    parser.add_argument("--format", choices=("json", "github-output"), default="json")
    parser.add_argument("--version")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = resolve_release_env(
        environ=os.environ,
        version_override=args.version,
    )

    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return 0

    for key, value in payload.items():
        print(f"{key}={value}")
    return 0


def resolve_release_env(
    *,
    environ: dict[str, str],
    version_override: str | None = None,
) -> dict[str, str]:
    config = _load_project_config(REPO_ROOT / "config" / "project.toml")
    project = config["project"]
    runtime = config["runtime"]
    distribution = config["distribution"]

    repository = environ.get("GITHUB_REPOSITORY", "")
    repository_owner = environ.get("GITHUB_REPOSITORY_OWNER", "")
    repo_name = repository.split("/", 1)[1] if "/" in repository else project["slug"]
    owner_lower = repository_owner.lower()

    version = (
        version_override
        or environ.get("RELEASE_VERSION")
        or _version_from_github_ref(environ)
        or __version__
    )
    git_tag = f"v{version}"

    docker_namespace = environ.get("DOCKERHUB_NAMESPACE") or owner_lower or project["slug"]
    docker_image_name = environ.get("DOCKERHUB_IMAGE_NAME") or distribution["docker_image_name"]
    docker_registry = distribution["docker_registry"]

    custom_domain = _normalize_custom_domain(environ.get("CUSTOM_DOMAIN", ""))
    update_base_url = (
        environ.get("UPDATE_BASE_URL")
        or _default_update_base_url(
            custom_domain=custom_domain,
            owner=owner_lower,
            repo_name=repo_name,
        )
    ).rstrip("/")

    docker_image = f"{docker_registry}/{docker_namespace}/{docker_image_name}:{version}"
    docker_image_latest = f"{docker_registry}/{docker_namespace}/{docker_image_name}:latest"

    return {
        "project_display_name": project["display_name"],
        "project_slug": project["slug"],
        "default_channel": project["default_channel"],
        "runtime_home_dir": runtime["home_dir"],
        "heartbeat_interval_seconds": str(runtime["heartbeat_interval_seconds"]),
        "docker_project_name": runtime["docker_project_name"],
        "container_name": runtime["container_name"],
        "repo_name": repo_name,
        "repo_owner": repository_owner,
        "docker_registry": docker_registry,
        "docker_namespace": docker_namespace,
        "docker_image_name": docker_image_name,
        "docker_image": docker_image,
        "docker_image_latest": docker_image_latest,
        "update_base_url": update_base_url,
        "custom_domain": custom_domain,
        "version": version,
        "git_tag": git_tag,
    }


def _load_project_config(path: Path) -> dict[str, dict[str, str | int]]:
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"Invalid project config at {path}"
        raise ValueError(msg)

    project = _require_section(payload, "project")
    runtime = _require_section(payload, "runtime")
    distribution = _require_section(payload, "distribution")

    return {
        "project": {
            "display_name": _require_str(project, "display_name"),
            "slug": _require_str(project, "slug"),
            "default_channel": _require_str(project, "default_channel"),
        },
        "runtime": {
            "home_dir": _require_str(runtime, "home_dir"),
            "heartbeat_interval_seconds": _require_int(runtime, "heartbeat_interval_seconds"),
            "docker_project_name": _require_str(runtime, "docker_project_name"),
            "container_name": _require_str(runtime, "container_name"),
        },
        "distribution": {
            "docker_registry": _require_str(distribution, "docker_registry"),
            "docker_image_name": _require_str(distribution, "docker_image_name"),
        },
    }


def _version_from_github_ref(environ: dict[str, str]) -> str | None:
    if environ.get("GITHUB_REF_TYPE") != "tag":
        return None
    ref_name = environ.get("GITHUB_REF_NAME", "")
    if ref_name.startswith("v"):
        return ref_name[1:]
    return ref_name or None


def _default_update_base_url(*, custom_domain: str, owner: str, repo_name: str) -> str:
    if custom_domain:
        return f"https://{custom_domain}"
    if owner and repo_name:
        return f"https://{owner}.github.io/{repo_name}"
    return ""


def _normalize_custom_domain(value: str) -> str:
    current = value.strip().rstrip("/")
    if not current:
        return ""

    if "://" in current:
        parsed = urlparse(current)
        if parsed.path not in {"", "/"}:
            msg = "CUSTOM_DOMAIN must be a host only, without a path."
            raise ValueError(msg)
        current = parsed.netloc

    if "/" in current:
        msg = "CUSTOM_DOMAIN must be a host only, without a path."
        raise ValueError(msg)

    return current


def _require_section(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        msg = f"Missing config section {key!r}"
        raise ValueError(msg)
    return value


def _require_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        msg = f"Config field {key!r} must be a non-empty string."
        raise ValueError(msg)
    return value


def _require_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        msg = f"Config field {key!r} must be an integer."
        raise ValueError(msg)
    return value


if __name__ == "__main__":
    raise SystemExit(main())
