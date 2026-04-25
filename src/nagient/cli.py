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

    init_parser = subparsers.add_parser("init", help="Write default runtime config files")
    init_parser.add_argument("--force", action="store_true")
    init_parser.add_argument("--format", choices=("text", "json"), default="text")

    status_parser = subparsers.add_parser("status", help="Show runtime and activation status")
    status_parser.add_argument("--format", choices=("text", "json"), default="text")

    doctor_parser = subparsers.add_parser("doctor", help="Show effective runtime settings")
    doctor_parser.add_argument("--format", choices=("text", "json"), default="text")

    preflight_parser = subparsers.add_parser(
        "preflight",
        help="Validate config and transport plugins",
    )
    preflight_parser.add_argument("--format", choices=("text", "json"), default="text")

    reconcile_parser = subparsers.add_parser(
        "reconcile",
        help="Validate and activate runtime config",
    )
    reconcile_parser.add_argument("--format", choices=("text", "json"), default="text")

    serve_parser = subparsers.add_parser("serve", help="Run the placeholder agent loop")
    serve_parser.add_argument("--once", action="store_true", help="Write one heartbeat and exit")

    transport_parser = subparsers.add_parser("transport", help="Manage transport plugins")
    transport_subparsers = transport_parser.add_subparsers(
        dest="transport_command",
        required=True,
    )
    transport_list_parser = transport_subparsers.add_parser(
        "list",
        help="List discovered transport plugins",
    )
    transport_list_parser.add_argument("--format", choices=("text", "json"), default="text")
    transport_scaffold_parser = transport_subparsers.add_parser(
        "scaffold",
        help="Generate a custom transport plugin template",
    )
    transport_scaffold_parser.add_argument("--plugin-id", required=True)
    transport_scaffold_parser.add_argument("--output")
    transport_scaffold_parser.add_argument("--force", action="store_true")
    transport_scaffold_parser.add_argument("--format", choices=("text", "json"), default="text")

    provider_parser = subparsers.add_parser("provider", help="Manage provider plugins")
    provider_subparsers = provider_parser.add_subparsers(
        dest="provider_command",
        required=True,
    )
    provider_list_parser = provider_subparsers.add_parser(
        "list",
        help="List discovered provider plugins",
    )
    provider_list_parser.add_argument("--format", choices=("text", "json"), default="text")
    provider_scaffold_parser = provider_subparsers.add_parser(
        "scaffold",
        help="Generate a custom provider plugin template",
    )
    provider_scaffold_parser.add_argument("--plugin-id", required=True)
    provider_scaffold_parser.add_argument("--output")
    provider_scaffold_parser.add_argument("--force", action="store_true")
    provider_scaffold_parser.add_argument("--format", choices=("text", "json"), default="text")
    provider_models_parser = provider_subparsers.add_parser(
        "models",
        help="List models exposed by a configured provider profile",
    )
    provider_models_parser.add_argument("provider_id")
    provider_models_parser.add_argument("--format", choices=("text", "json"), default="text")

    auth_parser = subparsers.add_parser("auth", help="Manage provider authentication")
    auth_subparsers = auth_parser.add_subparsers(dest="auth_command", required=True)
    auth_status_parser = auth_subparsers.add_parser(
        "status",
        help="Show auth status for provider profiles",
    )
    auth_status_parser.add_argument("provider_id", nargs="?")
    auth_status_parser.add_argument("--verify", action="store_true")
    auth_status_parser.add_argument("--format", choices=("text", "json"), default="text")
    auth_login_parser = auth_subparsers.add_parser(
        "login",
        help="Login or register credentials for a provider profile",
    )
    auth_login_parser.add_argument("provider_id")
    auth_login_parser.add_argument("--api-key")
    auth_login_parser.add_argument("--token")
    auth_login_parser.add_argument("--secret-name")
    auth_login_parser.add_argument("--format", choices=("text", "json"), default="text")
    auth_complete_parser = auth_subparsers.add_parser(
        "complete",
        help="Complete a pending browser/device login session",
    )
    auth_complete_parser.add_argument("provider_id")
    auth_complete_parser.add_argument("--session-id", required=True)
    auth_complete_parser.add_argument("--callback-url")
    auth_complete_parser.add_argument("--code")
    auth_complete_parser.add_argument("--format", choices=("text", "json"), default="text")
    auth_logout_parser = auth_subparsers.add_parser(
        "logout",
        help="Delete stored credentials for a provider profile",
    )
    auth_logout_parser.add_argument("provider_id")
    auth_logout_parser.add_argument("--format", choices=("text", "json"), default="text")

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

    if args.command == "init":
        payload = container.configuration_service.initialize(force=args.force)
        return _emit(payload, args.format)

    if args.command in {"doctor", "status"}:
        payload = container.status_service.collect()
        return _emit(payload, args.format)

    if args.command == "preflight":
        payload = container.preflight_service.inspect().to_dict()
        return _emit(payload, args.format)

    if args.command == "reconcile":
        report = container.reconcile_service.reconcile()
        exit_code = 0 if report.can_activate else 1
        _emit(report.to_dict(), args.format)
        return exit_code

    if args.command == "serve":
        return container.runtime_agent.serve(once=args.once)

    if args.command == "transport" and args.transport_command == "list":
        discovery = container.plugin_registry.discover(container.settings.plugins_dir)
        payload = {
            "plugins": [
                {
                    "plugin_id": plugin.manifest.plugin_id,
                    "display_name": plugin.manifest.display_name,
                    "namespace": plugin.manifest.namespace,
                    "source": plugin.source,
                    "required_config": plugin.manifest.required_config,
                    "optional_config": plugin.manifest.optional_config,
                    "custom_functions": plugin.manifest.custom_functions,
                    "exposed_functions": plugin.manifest.exposed_functions,
                }
                for plugin in discovery.plugins.values()
            ],
            "issues": [issue.to_dict() for issue in discovery.issues],
        }
        return _emit(payload, args.format)

    if args.command == "transport" and args.transport_command == "scaffold":
        output_dir = Path(args.output) if args.output else None
        result = container.configuration_service.scaffold_transport(
            plugin_id=args.plugin_id,
            output_dir=output_dir,
            force=args.force,
        )
        return _emit(result.to_dict(), args.format)

    if args.command == "provider" and args.provider_command == "list":
        discovery = container.provider_registry.discover(container.settings.providers_dir)
        payload = {
            "plugins": [
                {
                    "plugin_id": plugin.manifest.plugin_id,
                    "display_name": plugin.manifest.display_name,
                    "family": plugin.manifest.family,
                    "source": plugin.source,
                    "supported_auth_modes": plugin.manifest.supported_auth_modes,
                    "default_auth_mode": plugin.manifest.default_auth_mode,
                    "capabilities": plugin.manifest.capabilities,
                    "required_config": plugin.manifest.required_config,
                    "optional_config": plugin.manifest.optional_config,
                    "secret_config": plugin.manifest.secret_config,
                }
                for plugin in discovery.plugins.values()
            ],
            "issues": [issue.to_dict() for issue in discovery.issues],
        }
        return _emit(payload, args.format)

    if args.command == "provider" and args.provider_command == "scaffold":
        output_dir = Path(args.output) if args.output else None
        result = container.configuration_service.scaffold_provider(
            plugin_id=args.plugin_id,
            output_dir=output_dir,
            force=args.force,
        )
        return _emit(result.to_dict(), args.format)

    if args.command == "provider" and args.provider_command == "models":
        payload = container.provider_service.list_models(args.provider_id)
        return _emit(payload, args.format)

    if args.command == "auth" and args.auth_command == "status":
        payload = container.provider_service.auth_status(
            provider_id=args.provider_id,
            verify_remote=args.verify,
        )
        return _emit(payload, args.format)

    if args.command == "auth" and args.auth_command == "login":
        payload = container.provider_service.login(
            args.provider_id,
            api_key=args.api_key,
            token=args.token,
            secret_name=args.secret_name,
        )
        return _emit(payload, args.format)

    if args.command == "auth" and args.auth_command == "complete":
        payload = container.provider_service.complete_login(
            args.provider_id,
            args.session_id,
            callback_url=args.callback_url,
            code=args.code,
        )
        return _emit(payload, args.format)

    if args.command == "auth" and args.auth_command == "logout":
        payload = container.provider_service.logout(args.provider_id)
        return _emit(payload, args.format)

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
    _append_lines(lines, payload)
    return "\n".join(lines)


def _append_lines(lines: list[str], payload: dict[str, object], prefix: str = "") -> None:
    for key, value in payload.items():
        label = f"{prefix}{key}"
        if isinstance(value, dict):
            lines.append(f"{label}:")
            _append_lines(lines, value, prefix=f"{label}.")
        elif isinstance(value, list):
            lines.append(f"{label}:")
            for index, item in enumerate(value):
                if isinstance(item, dict):
                    lines.append(f"  [{index}]")
                    _append_lines(lines, item, prefix="    ")
                else:
                    lines.append(f"  - {item}")
        else:
            lines.append(f"{label}: {value}")
