from __future__ import annotations

import argparse
import json
from pathlib import Path

from nagient.app.container import build_container
from nagient.infrastructure.manifests import release_to_dict
from nagient.version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nagient", description="Nagient control plane CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("version", help="Print the current version")

    doctor_parser = subparsers.add_parser("doctor", help="Show effective runtime settings")
    doctor_parser.add_argument("--format", choices=("text", "json"), default="text")

    serve_parser = subparsers.add_parser("serve", help="Run the placeholder agent loop")
    serve_parser.add_argument("--once", action="store_true", help="Write one heartbeat and exit")

    update_parser = subparsers.add_parser("update", help="Inspect available updates")
    update_subparsers = update_parser.add_subparsers(dest="update_command", required=True)
    update_check = update_subparsers.add_parser("check", help="Check if an update exists")
    update_check.add_argument("--channel", default="stable")
    update_check.add_argument("--manifest-ref")
    update_check.add_argument("--current-version", default=__version__)
    update_check.add_argument("--format", choices=("text", "json"), default="text")

    manifest_parser = subparsers.add_parser("manifest", help="Render release metadata")
    manifest_subparsers = manifest_parser.add_subparsers(dest="manifest_command", required=True)
    render_parser = manifest_subparsers.add_parser("render", help="Render a release manifest")
    render_parser.add_argument("--version", required=True)
    render_parser.add_argument("--channel", default="stable")
    render_parser.add_argument("--base-url", required=True)
    render_parser.add_argument("--docker-image", required=True)
    render_parser.add_argument("--published-at", default="1970-01-01T00:00:00Z")
    render_parser.add_argument("--summary", default="Initial scaffold release.")
    render_parser.add_argument("--output")

    migrations_parser = subparsers.add_parser("migrations", help="Plan upgrade migrations")
    migrations_subparsers = migrations_parser.add_subparsers(
        dest="migrations_command",
        required=True,
    )
    plan_parser = migrations_subparsers.add_parser("plan", help="List required migration steps")
    plan_parser.add_argument("--manifest-ref", required=True)
    plan_parser.add_argument("--current-version", required=True)
    plan_parser.add_argument("--format", choices=("text", "json"), default="text")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    container = build_container()

    if args.command == "version":
        print(__version__)
        return 0

    if args.command == "doctor":
        payload = container.health_service.collect()
        return _emit(payload, args.format)

    if args.command == "serve":
        return container.runtime_agent.serve(once=args.once)

    if args.command == "update" and args.update_command == "check":
        notice = container.update_service.check(
            current_version=args.current_version,
            channel=args.channel,
            manifest_ref=args.manifest_ref,
        )
        payload = {
            "current_version": str(notice.current_version),
            "target_version": str(notice.target_version),
            "update_available": notice.update_available,
            "message": notice.message,
            "planned_migrations": [
                {
                    "id": step.step_id,
                    "from_version": str(step.from_version),
                    "to_version": str(step.to_version),
                    "description": step.description,
                    "command": step.command,
                }
                for step in notice.planned_migrations
            ],
            "manifest": release_to_dict(notice.manifest) if notice.manifest else None,
        }
        return _emit(payload, args.format)

    if args.command == "manifest" and args.manifest_command == "render":
        payload = _build_release_manifest_payload(
            version=args.version,
            channel=args.channel,
            base_url=args.base_url,
            docker_image=args.docker_image,
            published_at=args.published_at,
            summary=args.summary,
        )
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return _emit(payload, "json")

    if args.command == "migrations" and args.migrations_command == "plan":
        notice = container.update_service.check(
            current_version=args.current_version,
            manifest_ref=args.manifest_ref,
        )
        payload = {
            "current_version": str(notice.current_version),
            "target_version": str(notice.target_version),
            "planned_migrations": [
                {
                    "id": step.step_id,
                    "from_version": str(step.from_version),
                    "to_version": str(step.to_version),
                    "description": step.description,
                    "command": step.command,
                }
                for step in notice.planned_migrations
            ],
        }
        return _emit(payload, args.format)

    parser.error("Unsupported command.")
    return 2


def _build_release_manifest_payload(
    *,
    version: str,
    channel: str,
    base_url: str,
    docker_image: str,
    published_at: str,
    summary: str,
) -> dict[str, object]:
    version_base_url = f"{base_url.rstrip('/')}/{version}"
    return {
        "version": version,
        "channel": channel,
        "published_at": published_at,
        "summary": summary,
        "docker": {
            "image": docker_image,
            "compose_url": f"{version_base_url}/docker-compose.yml",
        },
        "artifacts": [
            {
                "name": "install.sh",
                "url": f"{version_base_url}/install.sh",
                "kind": "installer",
                "platform": "linux-macos",
            },
            {
                "name": "update.sh",
                "url": f"{version_base_url}/update.sh",
                "kind": "installer",
                "platform": "linux-macos",
            },
            {
                "name": "uninstall.sh",
                "url": f"{version_base_url}/uninstall.sh",
                "kind": "installer",
                "platform": "linux-macos",
            },
            {
                "name": "install.ps1",
                "url": f"{version_base_url}/install.ps1",
                "kind": "installer",
                "platform": "windows",
            },
            {
                "name": "update.ps1",
                "url": f"{version_base_url}/update.ps1",
                "kind": "installer",
                "platform": "windows",
            },
            {
                "name": "uninstall.ps1",
                "url": f"{version_base_url}/uninstall.ps1",
                "kind": "installer",
                "platform": "windows",
            },
            {
                "name": "docker-compose.yml",
                "url": f"{version_base_url}/docker-compose.yml",
                "kind": "deployment",
                "platform": "any",
            },
        ],
        "migrations": [
            {
                "id": f"state-sync-{version}",
                "from_version": "0.0.0",
                "to_version": version,
                "description": (
                    "Sync runtime state and persisted metadata to the new release format."
                ),
                "command": "nagient migrations sync-state",
            }
        ],
        "notices": [
            "Release metadata is generated by CI and powers install/update flows.",
        ],
    }


def _emit(payload: dict[str, object], output_format: str) -> int:
    if output_format == "json":
        print(json.dumps(payload, indent=2))
        return 0

    print(_render_text(payload))
    return 0


def _render_text(payload: dict[str, object]) -> str:
    lines: list[str] = []
    for key, value in payload.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for nested_key, nested_value in value.items():
                lines.append(f"  {nested_key}: {nested_value}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)
