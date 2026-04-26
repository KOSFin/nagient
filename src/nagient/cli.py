from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from nagient.app.configuration import load_runtime_configuration
from nagient.app.container import build_container
from nagient.domain.entities.agent_runtime import AgentTurnRequest
from nagient.domain.entities.tooling import ToolExecutionRequest
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
    status_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show the full diagnostic tree instead of the compact summary",
    )

    paths_parser = subparsers.add_parser(
        "paths",
        help="Show path aliases and resolved runtime paths",
    )
    paths_parser.add_argument("--format", choices=("text", "json"), default="text")

    doctor_parser = subparsers.add_parser("doctor", help="Show detailed runtime diagnostics")
    doctor_parser.add_argument("--format", choices=("text", "json"), default="text")
    doctor_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show the full raw diagnostic tree",
    )

    preflight_parser = subparsers.add_parser(
        "preflight",
        help="Validate config and transport plugins",
    )
    preflight_parser.add_argument("--format", choices=("text", "json"), default="text")
    preflight_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show the full raw diagnostic tree",
    )

    reconcile_parser = subparsers.add_parser(
        "reconcile",
        help="Validate and activate runtime config",
    )
    reconcile_parser.add_argument("--format", choices=("text", "json"), default="text")
    reconcile_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show the full raw diagnostic tree",
    )

    serve_parser = subparsers.add_parser("serve", help="Run the placeholder agent loop")
    serve_parser.add_argument("--once", action="store_true", help="Write one heartbeat and exit")

    setup_parser = subparsers.add_parser(
        "setup",
        help="Open the interactive setup wizard or configure runtime components",
        description=(
            "Without a subcommand, open the interactive setup wizard. "
            "All setup menus use 0 to go back or exit."
        ),
    )
    setup_subparsers = setup_parser.add_subparsers(dest="setup_command", required=False)

    setup_provider_parser = setup_subparsers.add_parser(
        "provider",
        help="Configure a provider profile",
    )
    setup_provider_parser.add_argument("provider_id")
    setup_provider_parser.add_argument("--plugin")
    setup_provider_parser.add_argument("--enable", action="store_true")
    setup_provider_parser.add_argument("--disable", action="store_true")
    setup_provider_parser.add_argument("--default", action="store_true")
    setup_provider_parser.add_argument("--not-default", action="store_true")
    setup_provider_parser.add_argument("--auth")
    setup_provider_parser.add_argument("--model")
    setup_provider_parser.add_argument("--secret-name")
    setup_provider_parser.add_argument("--base-url")
    setup_provider_parser.add_argument("--fetch-models", action="store_true")
    setup_provider_parser.add_argument("--select-model", action="store_true")
    setup_provider_parser.add_argument("--set", action="append", default=[])
    setup_provider_parser.add_argument("--format", choices=("text", "json"), default="text")

    setup_transport_parser = setup_subparsers.add_parser(
        "transport",
        help="Configure a transport profile",
    )
    setup_transport_parser.add_argument("transport_id")
    setup_transport_parser.add_argument("--plugin")
    setup_transport_parser.add_argument("--enable", action="store_true")
    setup_transport_parser.add_argument("--disable", action="store_true")
    setup_transport_parser.add_argument("--set", action="append", default=[])
    setup_transport_parser.add_argument("--format", choices=("text", "json"), default="text")

    setup_tool_parser = setup_subparsers.add_parser(
        "tool",
        help="Configure a tool profile",
    )
    setup_tool_parser.add_argument("tool_id")
    setup_tool_parser.add_argument("--plugin")
    setup_tool_parser.add_argument("--enable", action="store_true")
    setup_tool_parser.add_argument("--disable", action="store_true")
    setup_tool_parser.add_argument("--set", action="append", default=[])
    setup_tool_parser.add_argument("--format", choices=("text", "json"), default="text")

    setup_workspace_parser = setup_subparsers.add_parser(
        "workspace",
        help="Configure workspace settings",
    )
    setup_workspace_parser.add_argument("--root")
    setup_workspace_parser.add_argument("--mode", choices=("bounded", "unsafe"))
    setup_workspace_parser.add_argument("--format", choices=("text", "json"), default="text")

    setup_paths_parser = setup_subparsers.add_parser(
        "paths",
        help="Configure config-linked runtime paths",
    )
    setup_paths_parser.add_argument("--secrets-file")
    setup_paths_parser.add_argument("--tool-secrets-file")
    setup_paths_parser.add_argument("--plugins-dir")
    setup_paths_parser.add_argument("--tools-dir")
    setup_paths_parser.add_argument("--providers-dir")
    setup_paths_parser.add_argument("--credentials-dir")
    setup_paths_parser.add_argument("--format", choices=("text", "json"), default="text")

    chat_parser = subparsers.add_parser(
        "chat",
        help="Talk to the default provider through the CLI console transport",
        description=(
            "Open a direct CLI console chat against the selected provider or the "
            "configured default provider."
        ),
    )
    chat_parser.add_argument("message", nargs="?")
    chat_parser.add_argument("--provider")
    chat_parser.add_argument("--system")
    chat_parser.add_argument("--interactive", action="store_true")
    chat_parser.add_argument("--format", choices=("text", "json"), default="text")

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

    tool_parser = subparsers.add_parser("tool", help="Manage and invoke tool plugins")
    tool_subparsers = tool_parser.add_subparsers(dest="tool_command", required=True)
    tool_list_parser = tool_subparsers.add_parser("list", help="List discovered tool plugins")
    tool_list_parser.add_argument("--format", choices=("text", "json"), default="text")
    tool_scaffold_parser = tool_subparsers.add_parser(
        "scaffold",
        help="Generate a custom tool plugin template",
    )
    tool_scaffold_parser.add_argument("--plugin-id", required=True)
    tool_scaffold_parser.add_argument("--output")
    tool_scaffold_parser.add_argument("--force", action="store_true")
    tool_scaffold_parser.add_argument("--format", choices=("text", "json"), default="text")
    tool_invoke_parser = tool_subparsers.add_parser(
        "invoke",
        help="Invoke a configured tool function",
    )
    tool_invoke_parser.add_argument("function_name")
    tool_invoke_parser.add_argument("--tool-id")
    tool_invoke_parser.add_argument("--args-json", default="{}")
    tool_invoke_parser.add_argument("--dry-run", action="store_true")
    tool_invoke_parser.add_argument("--auto-approve", action="store_true")
    tool_invoke_parser.add_argument("--format", choices=("text", "json"), default="text")

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

    interaction_parser = subparsers.add_parser(
        "interaction",
        help="Inspect and submit secure interaction requests",
    )
    interaction_subparsers = interaction_parser.add_subparsers(
        dest="interaction_command",
        required=True,
    )
    interaction_list_parser = interaction_subparsers.add_parser(
        "list",
        help="List secure interaction requests",
    )
    interaction_list_parser.add_argument("--format", choices=("text", "json"), default="text")
    interaction_submit_parser = interaction_subparsers.add_parser(
        "submit",
        help="Submit a response to a secure interaction request",
    )
    interaction_submit_parser.add_argument("request_id")
    interaction_submit_parser.add_argument("--response")
    interaction_submit_parser.add_argument("--cancel", action="store_true")
    interaction_submit_parser.add_argument("--format", choices=("text", "json"), default="text")

    approval_parser = subparsers.add_parser(
        "approval",
        help="Inspect and resolve approval requests",
    )
    approval_subparsers = approval_parser.add_subparsers(
        dest="approval_command",
        required=True,
    )
    approval_list_parser = approval_subparsers.add_parser(
        "list",
        help="List approval requests",
    )
    approval_list_parser.add_argument("--format", choices=("text", "json"), default="text")
    approval_respond_parser = approval_subparsers.add_parser(
        "respond",
        help="Resolve an approval request",
    )
    approval_respond_parser.add_argument("request_id")
    approval_respond_parser.add_argument(
        "--decision",
        required=True,
        choices=("approve", "reject", "cancel"),
    )
    approval_respond_parser.add_argument("--format", choices=("text", "json"), default="text")

    agent_parser = subparsers.add_parser("agent", help="Run structured agent-turn workflows")
    agent_subparsers = agent_parser.add_subparsers(dest="agent_command", required=True)
    agent_turn_parser = agent_subparsers.add_parser(
        "turn",
        help="Execute a structured agent turn payload",
    )
    agent_turn_parser.add_argument("--request-file", required=True)
    agent_turn_parser.add_argument("--format", choices=("text", "json"), default="text")

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

    if args.command == "status":
        payload = container.status_service.collect()
        return _emit(payload, args.format, view="status", verbose=args.verbose)

    if args.command == "paths":
        payload = _paths_payload(container)
        return _emit(payload, args.format, view="paths")

    if args.command == "doctor":
        payload = container.status_service.collect()
        return _emit(payload, args.format, view="doctor", verbose=args.verbose)

    if args.command == "preflight":
        payload = container.preflight_service.inspect().to_dict()
        return _emit(payload, args.format, view="preflight", verbose=args.verbose)

    if args.command == "reconcile":
        report = container.reconcile_service.reconcile()
        exit_code = 0 if report.can_activate else 1
        _emit(report.to_dict(), args.format, view="reconcile", verbose=args.verbose)
        return exit_code

    if args.command == "serve":
        return container.runtime_agent.serve(once=args.once)

    if args.command == "setup" and args.setup_command is None:
        return _run_setup_wizard(container)

    if args.command == "setup" and args.setup_command == "provider":
        config_updates = _parse_assignment_pairs(args.set)
        if args.auth is not None:
            config_updates["auth"] = args.auth
        if args.model is not None:
            config_updates["model"] = args.model
        if args.secret_name is not None:
            config_updates["api_key_secret"] = args.secret_name
        if args.base_url is not None:
            config_updates["base_url"] = args.base_url

        payload = container.configuration_service.configure_provider(
            args.provider_id,
            plugin_id=args.plugin,
            enabled=_resolve_enablement(args.enable, args.disable),
            default=_resolve_default_flag(args.default, args.not_default),
            config_updates=config_updates,
        )

        should_select_model = args.select_model and args.model is None
        if args.fetch_models or should_select_model:
            models_payload = container.configuration_service.select_provider_model(
                args.provider_id
            )
            models = models_payload.get("models", [])
            if not isinstance(models, list):
                models = []
            payload = dict(payload)
            payload["models"] = models
            if should_select_model:
                selected_model = _prompt_for_model_selection(models)
                if selected_model is not None:
                    payload = container.configuration_service.configure_provider(
                        args.provider_id,
                        config_updates={"model": selected_model},
                    )
                    payload["selected_model"] = selected_model
                    payload["models"] = models
        return _emit(payload, args.format)

    if args.command == "setup" and args.setup_command == "transport":
        payload = container.configuration_service.configure_transport(
            args.transport_id,
            plugin_id=args.plugin,
            enabled=_resolve_enablement(args.enable, args.disable),
            config_updates=_parse_assignment_pairs(args.set),
        )
        return _emit(payload, args.format)

    if args.command == "setup" and args.setup_command == "tool":
        payload = container.configuration_service.configure_tool(
            args.tool_id,
            plugin_id=args.plugin,
            enabled=_resolve_enablement(args.enable, args.disable),
            config_updates=_parse_assignment_pairs(args.set),
        )
        return _emit(payload, args.format)

    if args.command == "setup" and args.setup_command == "workspace":
        payload = container.configuration_service.configure_workspace(
            root=_resolve_path_alias(args.root, container.settings) if args.root else None,
            mode=args.mode,
        )
        return _emit(payload, args.format)

    if args.command == "setup" and args.setup_command == "paths":
        payload = container.configuration_service.configure_paths(
            {
                key: value
                for key, value in {
                    "secrets_file": _resolve_path_alias(
                        args.secrets_file, container.settings
                    )
                    if args.secrets_file
                    else None,
                    "tool_secrets_file": _resolve_path_alias(
                        args.tool_secrets_file, container.settings
                    )
                    if args.tool_secrets_file
                    else None,
                    "plugins_dir": _resolve_path_alias(
                        args.plugins_dir, container.settings
                    )
                    if args.plugins_dir
                    else None,
                    "tools_dir": _resolve_path_alias(args.tools_dir, container.settings)
                    if args.tools_dir
                    else None,
                    "providers_dir": _resolve_path_alias(
                        args.providers_dir, container.settings
                    )
                    if args.providers_dir
                    else None,
                    "credentials_dir": _resolve_path_alias(
                        args.credentials_dir, container.settings
                    )
                    if args.credentials_dir
                    else None,
                }.items()
                if value is not None
            }
        )
        return _emit(payload, args.format)

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
        transport_result = container.configuration_service.scaffold_transport(
            plugin_id=args.plugin_id,
            output_dir=output_dir,
            force=args.force,
        )
        return _emit(transport_result.to_dict(), args.format)

    if args.command == "provider" and args.provider_command == "list":
        provider_discovery = container.provider_registry.discover(
            container.settings.providers_dir
        )
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
                for plugin in provider_discovery.plugins.values()
            ],
            "issues": [issue.to_dict() for issue in provider_discovery.issues],
        }
        return _emit(payload, args.format)

    if args.command == "provider" and args.provider_command == "scaffold":
        output_dir = Path(args.output) if args.output else None
        provider_result = container.configuration_service.scaffold_provider(
            plugin_id=args.plugin_id,
            output_dir=output_dir,
            force=args.force,
        )
        return _emit(provider_result.to_dict(), args.format)

    if args.command == "provider" and args.provider_command == "models":
        payload = container.provider_service.list_models(args.provider_id)
        return _emit(payload, args.format)

    if args.command == "tool" and args.tool_command == "list":
        payload = container.tool_service.list_tools()
        return _emit(payload, args.format)

    if args.command == "tool" and args.tool_command == "scaffold":
        output_dir = Path(args.output) if args.output else None
        tool_scaffold_result = container.configuration_service.scaffold_tool(
            plugin_id=args.plugin_id,
            output_dir=output_dir,
            force=args.force,
        )
        return _emit(tool_scaffold_result.to_dict(), args.format)

    if args.command == "tool" and args.tool_command == "invoke":
        tool_request = ToolExecutionRequest(
            tool_id=args.tool_id or "",
            function_name=args.function_name,
            arguments=_load_json_argument(args.args_json),
            dry_run=args.dry_run,
            auto_approve=args.auto_approve,
        )
        payload = container.tool_service.invoke(tool_request).to_dict()
        return _emit(payload, args.format)

    if args.command == "auth" and args.auth_command == "status":
        payload = container.provider_service.auth_status(
            provider_id=args.provider_id,
            verify_remote=args.verify,
        )
        return _emit(payload, args.format, view="auth_status")

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

    if args.command == "chat":
        if args.interactive or args.message is None:
            if args.format != "text":
                raise ValueError("Interactive chat currently supports only --format text.")
            return _run_chat_session(
                container,
                provider_id=args.provider,
                system_prompt=args.system,
            )
        payload = container.provider_service.chat(
            provider_id=args.provider,
            message=args.message,
            system_prompt=args.system,
        )
        return _emit(payload, args.format, view="chat")

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
        return _emit(payload, args.format, view="update_check")

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

    if args.command == "interaction" and args.interaction_command == "list":
        payload = {
            "interactions": [
                request.to_dict()
                for request in container.workflow_service.list_interactions()
            ]
        }
        return _emit(payload, args.format)

    if args.command == "interaction" and args.interaction_command == "submit":
        response = args.response
        if not args.cancel and response is None:
            response = _read_secret_input(
                prompt=f"Enter secure response for interaction {args.request_id}: "
            )
        payload = container.workflow_service.submit_interaction(
            args.request_id,
            response=response,
            cancel=args.cancel,
        ).to_dict()
        return _emit(payload, args.format)

    if args.command == "approval" and args.approval_command == "list":
        payload = {
            "approvals": [
                request.to_dict()
                for request in container.workflow_service.list_approvals()
            ]
        }
        return _emit(payload, args.format)

    if args.command == "approval" and args.approval_command == "respond":
        payload = container.workflow_service.resolve_approval(
            args.request_id,
            args.decision,
        ).to_dict()
        return _emit(payload, args.format)

    if args.command == "agent" and args.agent_command == "turn":
        request_payload = json.loads(Path(args.request_file).read_text(encoding="utf-8"))
        if not isinstance(request_payload, dict):
            raise ValueError("Agent request payload must be a JSON object.")
        agent_turn_result = container.agent_turn_service.run_turn(
            AgentTurnRequest.from_dict(request_payload)
        )
        return _emit(agent_turn_result.to_dict(), args.format)

    parser.error("Unsupported command.")
    return 2


def _run_setup_wizard(container: object) -> int:
    while True:
        runtime_config = load_runtime_configuration(container.settings)
        default_provider = runtime_config.default_provider or "none"
        print("")
        print("Nagient Setup")
        print(f"Default provider: {default_provider}")
        selection = _prompt_menu_choice(
            "Choose a setup area:",
            [
                ("providers", "Providers"),
                ("transports", "Transports"),
                ("tools", "Tools"),
                ("workspace", "Workspace"),
                ("paths", "Path aliases"),
                ("auth", "Authentication"),
                ("chat", "Agent console"),
                ("status", "Show status"),
            ],
            zero_label="Exit setup",
        )
        if selection is None:
            print("Leaving setup.")
            return 0
        if selection == "providers":
            _run_provider_setup_menu(container)
            continue
        if selection == "transports":
            _run_transport_setup_menu(container)
            continue
        if selection == "tools":
            _run_tool_setup_menu(container)
            continue
        if selection == "workspace":
            _run_workspace_setup_menu(container)
            continue
        if selection == "paths":
            _run_paths_setup_menu(container)
            continue
        if selection == "auth":
            _run_auth_setup_menu(container)
            continue
        if selection == "chat":
            _run_chat_session(container, provider_id=None, system_prompt=None)
            continue
        if selection == "status":
            _emit(container.status_service.collect(), "text", view="status")


def _run_provider_setup_menu(container: object) -> None:
    while True:
        runtime_config = load_runtime_configuration(container.settings)
        options = [
            (
                provider.provider_id,
                _describe_provider_profile(provider, runtime_config.default_provider),
            )
            for provider in runtime_config.providers
        ]
        selection = _prompt_menu_choice(
            "Choose a provider profile:",
            options,
            zero_label="Back",
        )
        if selection is None:
            return
        _run_provider_profile_menu(container, selection)


def _run_provider_profile_menu(container: object, provider_id: str) -> None:
    while True:
        runtime_config = load_runtime_configuration(container.settings)
        provider = next(
            item for item in runtime_config.providers if item.provider_id == provider_id
        )
        discovery = container.provider_registry.discover(container.settings.providers_dir)
        plugin = discovery.plugins.get(provider.plugin_id)
        if plugin is None:
            print(f"Provider plugin {provider.plugin_id!r} is missing.")
            return
        manifest = plugin.manifest
        config = dict(provider.config)
        enabled_label = "Disable profile" if provider.enabled else "Enable profile"
        default_label = (
            "Unset as default provider"
            if runtime_config.default_provider == provider_id
            else "Set as default provider"
        )
        options: list[tuple[str, str]] = [
            ("toggle", enabled_label),
            ("default", default_label),
            (
                "auth",
                "Auth mode"
                + _suffix_value(_as_text(config.get("auth", manifest.default_auth_mode))),
            ),
            ("model", "Model" + _suffix_value(_as_text(config.get("model")))),
        ]
        if "api_key_secret" in manifest.allowed_config:
            options.append(
                (
                    "secret",
                    "API key secret" + _suffix_value(_as_text(config.get("api_key_secret"))),
                )
            )
        if "base_url" in manifest.allowed_config:
            options.append(
                ("base_url", "Base URL" + _suffix_value(_as_text(config.get("base_url"))))
            )
        options.extend(
            [
                ("advanced", "Advanced config fields"),
                ("login", "Run auth/login flow"),
                ("status", "Show auth status"),
            ]
        )
        if callable(getattr(plugin.implementation, "generate_message", None)):
            options.append(("chat", "Open agent console with this provider"))

        selection = _prompt_menu_choice(
            f"Provider {provider_id}:",
            options,
            zero_label="Back",
        )
        if selection is None:
            return
        if selection == "toggle":
            payload = container.configuration_service.configure_provider(
                provider_id,
                enabled=not provider.enabled,
            )
            _emit(payload, "text")
            continue
        if selection == "default":
            payload = container.configuration_service.configure_provider(
                provider_id,
                default=runtime_config.default_provider != provider_id,
            )
            _emit(payload, "text")
            continue
        if selection == "auth":
            auth_mode = _prompt_menu_choice(
                "Choose auth mode:",
                [(item, item) for item in manifest.supported_auth_modes],
                zero_label="Back",
            )
            if auth_mode is not None:
                payload = container.configuration_service.configure_provider(
                    provider_id,
                    config_updates={"auth": auth_mode},
                )
                _emit(payload, "text")
            continue
        if selection == "model":
            _interactive_select_provider_model(container, provider_id, current_model=config.get("model"))
            continue
        if selection == "secret":
            secret_name = _prompt_text(
                "API key secret",
                default=_as_text(config.get("api_key_secret")),
            )
            if secret_name is not None:
                payload = container.configuration_service.configure_provider(
                    provider_id,
                    config_updates={"api_key_secret": secret_name},
                )
                _emit(payload, "text")
            continue
        if selection == "base_url":
            base_url = _prompt_text("Base URL", default=_as_text(config.get("base_url")))
            if base_url is not None:
                payload = container.configuration_service.configure_provider(
                    provider_id,
                    config_updates={"base_url": base_url},
                )
                _emit(payload, "text")
            continue
        if selection == "advanced":
            _run_generic_field_editor(
                title=f"Provider {provider_id} fields:",
                current_config=config,
                allowed_keys=sorted(
                    key
                    for key in manifest.allowed_config
                    if key not in {"auth", "model", "api_key_secret", "base_url"}
                ),
                save_callback=lambda updates: container.configuration_service.configure_provider(
                    provider_id,
                    config_updates=updates,
                ),
            )
            continue
        if selection == "login":
            payload = container.provider_service.login(provider_id)
            _emit(payload, "text")
            continue
        if selection == "status":
            payload = container.provider_service.auth_status(provider_id)
            _emit(payload, "text", view="auth_status")
            continue
        if selection == "chat":
            _run_chat_session(container, provider_id=provider_id, system_prompt=None)


def _run_transport_setup_menu(container: object) -> None:
    while True:
        runtime_config = load_runtime_configuration(container.settings)
        options = [
            (transport.transport_id, _describe_transport_profile(transport))
            for transport in runtime_config.transports
        ]
        selection = _prompt_menu_choice(
            "Choose a transport profile:",
            options,
            zero_label="Back",
        )
        if selection is None:
            return
        _run_transport_profile_menu(container, selection)


def _run_transport_profile_menu(container: object, transport_id: str) -> None:
    while True:
        runtime_config = load_runtime_configuration(container.settings)
        transport = next(
            item for item in runtime_config.transports if item.transport_id == transport_id
        )
        discovery = container.plugin_registry.discover(container.settings.plugins_dir)
        plugin = discovery.plugins.get(transport.plugin_id)
        if plugin is None:
            print(f"Transport plugin {transport.plugin_id!r} is missing.")
            return
        selection = _prompt_menu_choice(
            f"Transport {transport_id}:",
            [
                ("toggle", "Disable profile" if transport.enabled else "Enable profile"),
                ("fields", "Edit config fields"),
            ],
            zero_label="Back",
        )
        if selection is None:
            return
        if selection == "toggle":
            payload = container.configuration_service.configure_transport(
                transport_id,
                enabled=not transport.enabled,
            )
            _emit(payload, "text")
            continue
        if selection == "fields":
            _run_generic_field_editor(
                title=f"Transport {transport_id} fields:",
                current_config=dict(transport.config),
                allowed_keys=sorted(plugin.manifest.allowed_config),
                save_callback=lambda updates: container.configuration_service.configure_transport(
                    transport_id,
                    config_updates=updates,
                ),
            )


def _run_tool_setup_menu(container: object) -> None:
    while True:
        runtime_config = load_runtime_configuration(container.settings)
        options = [(tool.tool_id, _describe_tool_profile(tool)) for tool in runtime_config.tools]
        selection = _prompt_menu_choice(
            "Choose a tool profile:",
            options,
            zero_label="Back",
        )
        if selection is None:
            return
        _run_tool_profile_menu(container, selection)


def _run_tool_profile_menu(container: object, tool_id: str) -> None:
    while True:
        runtime_config = load_runtime_configuration(container.settings)
        tool = next(item for item in runtime_config.tools if item.tool_id == tool_id)
        discovery = container.tool_registry.discover(container.settings.tools_dir)
        plugin = discovery.plugins.get(tool.plugin_id)
        if plugin is None:
            print(f"Tool plugin {tool.plugin_id!r} is missing.")
            return
        selection = _prompt_menu_choice(
            f"Tool {tool_id}:",
            [
                ("toggle", "Disable profile" if tool.enabled else "Enable profile"),
                ("fields", "Edit config fields"),
            ],
            zero_label="Back",
        )
        if selection is None:
            return
        if selection == "toggle":
            payload = container.configuration_service.configure_tool(
                tool_id,
                enabled=not tool.enabled,
            )
            _emit(payload, "text")
            continue
        if selection == "fields":
            _run_generic_field_editor(
                title=f"Tool {tool_id} fields:",
                current_config=dict(tool.config),
                allowed_keys=sorted(plugin.manifest.allowed_config),
                save_callback=lambda updates: container.configuration_service.configure_tool(
                    tool_id,
                    config_updates=updates,
                ),
            )


def _run_workspace_setup_menu(container: object) -> None:
    while True:
        runtime_config = load_runtime_configuration(container.settings)
        selection = _prompt_menu_choice(
            "Workspace settings:",
            [
                (
                    "root",
                    "Workspace root"
                    + _suffix_value(_render_path_value(str(runtime_config.workspace.root), container.settings)),
                ),
                ("mode", "Workspace mode" + _suffix_value(runtime_config.workspace.mode)),
            ],
            zero_label="Back",
        )
        if selection is None:
            return
        if selection == "root":
            root_value = _prompt_text(
                "Workspace root",
                default=_render_path_value(str(runtime_config.workspace.root), container.settings),
            )
            if root_value is not None:
                payload = container.configuration_service.configure_workspace(
                    root=_resolve_path_alias(root_value, container.settings)
                )
                _emit(payload, "text")
            continue
        if selection == "mode":
            mode = _prompt_menu_choice(
                "Choose workspace mode:",
                [("bounded", "bounded"), ("unsafe", "unsafe")],
                zero_label="Back",
            )
            if mode is not None:
                payload = container.configuration_service.configure_workspace(mode=mode)
                _emit(payload, "text")


def _run_paths_setup_menu(container: object) -> None:
    configurable_paths = {
        "@secrets": ("secrets_file", container.settings.secrets_file),
        "@tool_secrets": ("tool_secrets_file", container.settings.tool_secrets_file),
        "@plugins": ("plugins_dir", container.settings.plugins_dir),
        "@tools": ("tools_dir", container.settings.tools_dir),
        "@providers": ("providers_dir", container.settings.providers_dir),
        "@credentials": ("credentials_dir", container.settings.credentials_dir),
    }
    while True:
        selection = _prompt_menu_choice(
            "Choose a path alias to edit:",
            [
                (alias, f"{alias} -> {_render_path_value(str(path), container.settings)}")
                for alias, (_config_key, path) in configurable_paths.items()
            ],
            zero_label="Back",
        )
        if selection is None:
            return
        config_key, current_path = configurable_paths[selection]
        raw_value = _prompt_text(
            f"{selection}",
            default=_render_path_value(str(current_path), container.settings),
        )
        if raw_value is None:
            continue
        payload = container.configuration_service.configure_paths(
            {config_key: _resolve_path_alias(raw_value, container.settings)}
        )
        _emit(payload, "text")


def _run_auth_setup_menu(container: object) -> None:
    while True:
        runtime_config = load_runtime_configuration(container.settings)
        selection = _prompt_menu_choice(
            "Choose a provider for auth actions:",
            [
                (
                    provider.provider_id,
                    _describe_provider_profile(provider, runtime_config.default_provider),
                )
                for provider in runtime_config.providers
            ],
            zero_label="Back",
        )
        if selection is None:
            return
        action = _prompt_menu_choice(
            f"Auth actions for {selection}:",
            [
                ("status", "Show auth status"),
                ("login", "Run login flow"),
                ("logout", "Logout and remove stored credentials"),
            ],
            zero_label="Back",
        )
        if action is None:
            continue
        if action == "status":
            _emit(container.provider_service.auth_status(selection), "text", view="auth_status")
            continue
        if action == "login":
            _emit(container.provider_service.login(selection), "text")
            continue
        if action == "logout":
            _emit(container.provider_service.logout(selection), "text")


def _interactive_select_provider_model(
    container: object,
    provider_id: str,
    *,
    current_model: object,
) -> None:
    try:
        models_payload = container.configuration_service.select_provider_model(provider_id)
        selected_model = _prompt_for_model_selection(models_payload.get("models", []))
    except Exception:
        selected_model = None
    if selected_model is None:
        selected_model = _prompt_text("Model", default=_as_text(current_model))
    if selected_model is None:
        return
    payload = container.configuration_service.configure_provider(
        provider_id,
        config_updates={"model": selected_model},
    )
    _emit(payload, "text")


def _run_generic_field_editor(
    *,
    title: str,
    current_config: dict[str, object],
    allowed_keys: list[str],
    save_callback: object,
) -> None:
    if not allowed_keys:
        print("No extra config fields are available here.")
        return
    while True:
        selection = _prompt_menu_choice(
            title,
            [
                (
                    field_name,
                    field_name + _suffix_value(_as_text(current_config.get(field_name))),
                )
                for field_name in allowed_keys
            ],
            zero_label="Back",
        )
        if selection is None:
            return
        raw_value = _prompt_text(
            selection,
            default=_as_text(current_config.get(selection)),
        )
        if raw_value is None:
            continue
        payload = save_callback({selection: _coerce_cli_value(raw_value)})
        current_config[selection] = _coerce_cli_value(raw_value)
        _emit(payload, "text")


def _run_chat_session(
    container: object,
    *,
    provider_id: str | None,
    system_prompt: str | None,
) -> int:
    print("")
    print("Nagient Chat")
    print("Type your message and press Enter. Use 0, exit, or quit to leave.")
    while True:
        try:
            message = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("")
            return 0
        if not message:
            continue
        if message.lower() in {"0", "exit", "quit", "/exit"}:
            return 0
        payload = container.provider_service.chat(
            provider_id=provider_id,
            message=message,
            system_prompt=system_prompt,
        )
        print("")
        print(f"assistant> {payload['message']}")
        print("")


def _paths_payload(container: object) -> dict[str, object]:
    aliases = _path_aliases(container.settings)
    return {
        "aliases": [
            {"alias": alias, "path": path}
            for alias, path in aliases.items()
        ]
    }


def _path_aliases(settings: object) -> dict[str, str]:
    return {
        "@home": str(settings.home_dir),
        "@config": str(settings.config_file),
        "@config_dir": str(settings.config_file.parent),
        "@secrets": str(settings.secrets_file),
        "@tool_secrets": str(settings.tool_secrets_file),
        "@plugins": str(settings.plugins_dir),
        "@providers": str(settings.providers_dir),
        "@tools": str(settings.tools_dir),
        "@credentials": str(settings.credentials_dir),
        "@state": str(settings.state_dir),
        "@logs": str(settings.log_dir),
        "@releases": str(settings.releases_dir),
    }


def _resolve_path_alias(raw_value: str, settings: object) -> str:
    value = raw_value.strip()
    if not value:
        return value
    aliases = _path_aliases(settings)
    file_aliases = {"@config", "@secrets", "@tool_secrets"}
    for alias, resolved_path in aliases.items():
        if value == alias:
            return resolved_path
        for separator in ("/", os.sep):
            prefix = f"{alias}{separator}"
            if value.startswith(prefix):
                suffix = value[len(prefix) :]
                base = Path(resolved_path)
                if alias in file_aliases:
                    base = base.parent
                return str((base / suffix).expanduser())
    return str(Path(value).expanduser())


def _render_path_value(path: str, settings: object) -> str:
    aliases = _path_aliases(settings)
    normalized = str(Path(path).expanduser())
    sorted_aliases = sorted(
        aliases.items(),
        key=lambda item: len(item[1]),
        reverse=True,
    )
    for alias, resolved_path in sorted_aliases:
        if normalized == resolved_path:
            return alias
        prefix = resolved_path.rstrip("/\\") + os.sep
        if normalized.startswith(prefix):
            suffix = normalized[len(resolved_path.rstrip("/\\")) :].lstrip("/\\")
            return f"{alias}/{suffix}"
    return normalized


def _prompt_menu_choice(
    title: str,
    options: list[tuple[str, str]],
    *,
    zero_label: str,
) -> str | None:
    print("")
    print(title)
    for index, (_value, label) in enumerate(options, start=1):
        print(f"{index}) {label}")
    print(f"0) {zero_label}")
    try:
        raw_choice = input(f"Choice [0-{len(options)}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("")
        return None
    if not raw_choice or raw_choice == "0":
        return None
    if not raw_choice.isdigit():
        raise ValueError("Menu choice must be a number.")
    selected_index = int(raw_choice)
    if selected_index < 1 or selected_index > len(options):
        raise ValueError("Menu choice is out of range.")
    return options[selected_index - 1][0]


def _prompt_text(prompt: str, *, default: str = "") -> str | None:
    suffix = f" [{default}]" if default else ""
    try:
        raw_value = input(f"{prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("")
        return None
    if not raw_value:
        return default or None
    return raw_value


def _describe_provider_profile(provider: object, default_provider: str | None) -> str:
    label = provider.provider_id
    if default_provider == provider.provider_id:
        label += " [default]"
    label += " - "
    label += "enabled" if provider.enabled else "disabled"
    model = _as_text(provider.config.get("model"))
    if model:
        label += f", model {model}"
    return label


def _describe_transport_profile(transport: object) -> str:
    label = transport.transport_id + " - "
    label += "enabled" if transport.enabled else "disabled"
    return label


def _describe_tool_profile(tool: object) -> str:
    label = tool.tool_id + " - "
    label += "enabled" if tool.enabled else "disabled"
    return label


def _suffix_value(value: str) -> str:
    return f" [{value}]" if value else ""


def _parse_assignment_pairs(raw_pairs: list[str]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for raw_pair in raw_pairs:
        if "=" not in raw_pair:
            raise ValueError(
                f"Invalid assignment {raw_pair!r}. Expected the form key=value."
            )
        key, raw_value = raw_pair.split("=", 1)
        normalized_key = key.strip()
        if not normalized_key:
            raise ValueError("Assignment keys must not be empty.")
        payload[normalized_key] = _coerce_cli_value(raw_value.strip())
    return payload


def _coerce_cli_value(raw: str) -> object:
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _resolve_enablement(enable: bool, disable: bool) -> bool | None:
    if enable and disable:
        raise ValueError("Choose only one of --enable or --disable.")
    if enable:
        return True
    if disable:
        return False
    return None


def _resolve_default_flag(default: bool, not_default: bool) -> bool | None:
    if default and not_default:
        raise ValueError("Choose only one of --default or --not-default.")
    if default:
        return True
    if not_default:
        return False
    return None


def _prompt_for_model_selection(models: list[object]) -> str | None:
    normalized_models = [
        item for item in models if isinstance(item, dict) and item.get("model_id")
    ]
    if not normalized_models:
        return None

    print("Available models:")
    for index, model in enumerate(normalized_models, start=1):
        model_id = str(model.get("model_id", "")).strip()
        display_name = str(model.get("display_name", model_id)).strip()
        label = display_name if display_name else model_id
        print(f"{index}) {label} [{model_id}]")
    print("0) Back")

    try:
        selection = input(f"Model [0-{len(normalized_models)}]: ").strip()
    except EOFError:
        return None
    if not selection or selection == "0":
        return None
    if not selection.isdigit():
        raise ValueError("Model selection must be a number.")
    selected_index = int(selection)
    if selected_index < 1 or selected_index > len(normalized_models):
        raise ValueError("Model selection is out of range.")
    selected = normalized_models[selected_index - 1]
    return str(selected.get("model_id", "")).strip() or None


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


def _emit(
    payload: dict[str, object],
    output_format: str,
    *,
    view: str = "generic",
    verbose: bool = False,
) -> int:
    if output_format == "json":
        print(json.dumps(payload, indent=2))
        return 0

    print(_render_text(payload, view=view, verbose=verbose))
    return 0


def _load_json_argument(raw_value: str) -> dict[str, object]:
    payload = json.loads(raw_value)
    if not isinstance(payload, dict):
        raise ValueError("Tool arguments must decode to a JSON object.")
    return {str(key): value for key, value in payload.items()}


def _read_secret_input(prompt: str) -> str | None:
    try:
        return getpass.getpass(prompt=prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return None


def _render_text(payload: dict[str, object], *, view: str, verbose: bool) -> str:
    if verbose:
        verbose_lines: list[str] = []
        _append_lines(verbose_lines, payload)
        return "\n".join(verbose_lines)

    if view == "status":
        return _render_status_summary(payload)
    if view == "doctor":
        return _render_doctor_summary(payload)
    if view == "preflight":
        return _render_activation_summary(payload, title="Nagient Preflight")
    if view == "reconcile":
        return _render_activation_summary(payload, title="Nagient Reconcile")
    if view == "auth_status":
        return _render_auth_status(payload)
    if view == "update_check":
        return _render_update_check(payload)
    if view == "paths":
        return _render_paths_summary(payload)
    if view == "chat":
        return _render_chat_summary(payload)

    default_lines: list[str] = []
    _append_lines(default_lines, payload)
    return "\n".join(default_lines)


def _render_paths_summary(payload: dict[str, object]) -> str:
    colors = _supports_color()
    lines = [_heading("Nagient Paths", colors)]
    aliases = payload.get("aliases", [])
    if not isinstance(aliases, list) or not aliases:
        _append_line(lines, "No path aliases are available.")
        return "\n".join(lines)
    for item in aliases:
        alias_payload = _as_dict(item)
        alias = _as_text(alias_payload.get("alias"))
        path = _as_text(alias_payload.get("path"))
        if alias:
            _append_key_value(lines, alias, path)
    return "\n".join(lines)


def _render_chat_summary(payload: dict[str, object]) -> str:
    colors = _supports_color()
    lines = [_heading("Nagient Chat", colors)]
    provider_id = _as_text(payload.get("provider_id"))
    model = _as_text(payload.get("model"))
    if provider_id:
        _append_key_value(lines, "Provider", provider_id)
    if model:
        _append_key_value(lines, "Model", model)
    _append_section(lines, "Reply", colors)
    _append_line(lines, _as_text(payload.get("message")))
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


def _render_status_summary(payload: dict[str, object]) -> str:
    colors = _supports_color()
    lines = [_heading("Nagient Status", colors)]

    activation = _as_dict(payload.get("activation"))
    workspace = _as_dict(payload.get("workspace"))
    pending = _as_dict(payload.get("pending_workflows"))
    host_paths = _host_paths()

    _append_section(lines, "Overview", colors)
    _append_key_value(
        lines,
        "Runtime",
        _format_status(activation.get("status"), colors=colors),
    )
    _append_key_value(
        lines,
        "Version",
        _join_parts(
            _as_text(payload.get("version")),
            _as_text(payload.get("channel")),
            separator=" ",
            wrap_right="()",
        ),
    )
    _append_key_value(
        lines,
        "Safe mode",
        "on" if _as_bool(payload.get("safe_mode")) else "off",
    )
    if _has_value(activation.get("can_activate")):
        _append_key_value(
            lines,
            "Can activate",
            "yes" if _as_bool(activation.get("can_activate")) else "no",
        )
    if _as_int(pending.get("approvals")) or _as_int(pending.get("interactions")):
        _append_key_value(
            lines,
            "Pending",
            ", ".join(
                [
                    f"approvals {_as_int(pending.get('approvals'))}",
                    f"interactions {_as_int(pending.get('interactions'))}",
                ]
            ),
        )

    if host_paths:
        _append_section(lines, "Files", colors)
        for label, key in (
            ("@home", "home"),
            ("@config", "config"),
            ("@secrets", "secrets"),
            ("@tool_secrets", "tool_secrets"),
            ("@workspace", "workspace"),
        ):
            if key in host_paths:
                _append_key_value(lines, label, host_paths[key])

    _append_section(lines, "Workspace", colors)
    _append_key_value(
        lines,
        "Status",
        _format_status(workspace.get("status"), colors=colors),
    )
    _append_key_value(lines, "Mode", _as_text(workspace.get("mode")))
    _append_key_value(lines, "Root", _as_text(workspace.get("root")))
    _append_key_value(
        lines,
        "Backups",
        "on" if _as_bool(workspace.get("backup_enabled")) else "off",
    )
    _append_issue_block(
        lines,
        _as_list(workspace.get("issues")),
        colors=colors,
    )

    _append_component_section(
        lines,
        "Providers",
        _as_list(activation.get("providers")),
        kind="provider",
        colors=colors,
        detailed=False,
    )
    _append_component_section(
        lines,
        "Transports",
        _as_list(activation.get("transports")),
        kind="transport",
        colors=colors,
        detailed=False,
    )

    readiness_lines = _agent_readiness_lines(activation)
    if readiness_lines:
        _append_section(lines, "Agent Readiness", colors)
        for readiness_line in readiness_lines:
            _append_line(lines, readiness_line)

    tools = _as_list(activation.get("tools"))
    _append_section(lines, "Tools", colors)
    if tools:
        ready_count = sum(
            1 for item in tools if _normalized_status(_as_dict(item).get("status")) == "ready"
        )
        issue_count = sum(len(_as_list(_as_dict(item).get("issues"))) for item in tools)
        _append_key_value(lines, "Ready", f"{ready_count}/{len(tools)}")
        if issue_count:
            _append_key_value(lines, "Issues", str(issue_count))
    else:
        _append_line(lines, "No tool status is available yet.")

    _append_section(lines, "Secrets", colors)
    secrets = _as_dict(payload.get("secrets"))
    _append_key_value(lines, "Core", str(_as_int(secrets.get("core_count"))))
    _append_key_value(lines, "Tool", str(_as_int(secrets.get("tool_count"))))

    _append_section(lines, "Updates", colors)
    update = _as_dict(payload.get("update"))
    for line in _update_summary_lines(update, colors=colors):
        _append_line(lines, line)

    issues = _as_list(activation.get("issues"))
    notices = _as_list(activation.get("notices"))
    if issues:
        _append_section(lines, "Issues", colors)
        _append_issue_block(lines, issues, colors=colors)
    elif notices:
        _append_section(lines, "Notices", colors)
        for notice in notices:
            _append_line(lines, _as_text(notice))

    next_steps = _next_steps(payload)
    if next_steps:
        _append_section(lines, "Next Steps", colors)
        for step in next_steps:
            _append_line(lines, step)

    return "\n".join(lines)


def _render_doctor_summary(payload: dict[str, object]) -> str:
    colors = _supports_color()
    lines = [_heading("Nagient Doctor", colors)]

    activation = _as_dict(payload.get("activation"))
    workspace = _as_dict(payload.get("workspace"))
    pending = _as_dict(payload.get("pending_workflows"))
    update = _as_dict(payload.get("update"))
    effective_config = _as_dict(payload.get("effective_config"))
    effective_settings = _as_dict(effective_config.get("settings"))
    runtime_paths = _as_dict(payload.get("paths"))
    host_paths = _host_paths()

    _append_section(lines, "Overview", colors)
    _append_key_value(
        lines,
        "Runtime",
        _format_status(activation.get("status"), colors=colors),
    )
    _append_key_value(lines, "Version", _as_text(payload.get("version")))
    _append_key_value(lines, "Channel", _as_text(payload.get("channel")))
    _append_key_value(
        lines,
        "Safe mode",
        "on" if _as_bool(payload.get("safe_mode")) else "off",
    )
    _append_key_value(
        lines,
        "Default provider",
        _as_text(effective_config.get("default_provider")) or "none",
    )
    _append_key_value(
        lines,
        "Require provider",
        "yes" if _as_bool(effective_config.get("require_provider")) else "no",
    )
    if _has_value(effective_settings.get("heartbeat_interval_seconds")):
        _append_key_value(
            lines,
            "Heartbeat",
            f"{_as_text(effective_settings.get('heartbeat_interval_seconds'))}s",
        )
    _append_key_value(
        lines,
        "Pending approvals",
        str(_as_int(pending.get("approvals"))),
    )
    _append_key_value(
        lines,
        "Pending interactions",
        str(_as_int(pending.get("interactions"))),
    )

    if host_paths:
        _append_section(lines, "Host Files", colors)
        for label, key in (
            ("@home", "home"),
            ("@config", "config"),
            ("@secrets", "secrets"),
            ("@tool_secrets", "tool_secrets"),
            ("@workspace", "workspace"),
        ):
            if key in host_paths:
                _append_key_value(lines, label, host_paths[key])

    _append_section(lines, "Runtime Files", colors)
    for label, key in (
        ("@home", "home"),
        ("@config", "config"),
        ("@secrets", "secrets"),
        ("@tool_secrets", "tool_secrets"),
        ("@plugins", "plugins"),
        ("@tools", "tools"),
        ("@providers", "providers"),
        ("@credentials", "credentials"),
        ("@state", "state"),
        ("@logs", "logs"),
        ("@releases", "releases"),
    ):
        if key in runtime_paths:
            _append_key_value(lines, label, _as_text(runtime_paths[key]))

    _append_section(lines, "Workspace", colors)
    for label, key in (
        ("Status", "status"),
        ("Mode", "mode"),
        ("Root", "root"),
        ("Nagient dir", "nagient_dir"),
    ):
        value = workspace.get(key)
        if key == "status":
            _append_key_value(lines, label, _format_status(value, colors=colors))
        else:
            _append_key_value(lines, label, _as_text(value))
    _append_key_value(
        lines,
        "Backups",
        "on" if _as_bool(workspace.get("backup_enabled")) else "off",
    )
    _append_issue_block(lines, _as_list(workspace.get("issues")), colors=colors)

    _append_component_section(
        lines,
        "Providers",
        _as_list(activation.get("providers")),
        kind="provider",
        colors=colors,
        detailed=True,
    )
    _append_component_section(
        lines,
        "Transports",
        _as_list(activation.get("transports")),
        kind="transport",
        colors=colors,
        detailed=True,
    )
    _append_component_section(
        lines,
        "Tools",
        _as_list(activation.get("tools")),
        kind="tool",
        colors=colors,
        detailed=True,
    )

    _append_section(lines, "Updates", colors)
    _append_key_value(
        lines,
        "Center",
        _as_text(payload.get("update_base_url")) or "not configured",
    )
    for line in _update_summary_lines(update, colors=colors):
        _append_line(lines, line)

    notices = _as_list(activation.get("notices"))
    if notices:
        _append_section(lines, "Notices", colors)
        for notice in notices:
            _append_line(lines, _as_text(notice))

    issues = _as_list(activation.get("issues"))
    if issues:
        _append_section(lines, "Issues", colors)
        _append_issue_block(lines, issues, colors=colors)

    return "\n".join(lines)


def _render_activation_summary(payload: dict[str, object], *, title: str) -> str:
    colors = _supports_color()
    lines = [_heading(title, colors)]

    _append_section(lines, "Overview", colors)
    _append_key_value(lines, "Status", _format_status(payload.get("status"), colors=colors))
    _append_key_value(
        lines,
        "Can activate",
        "yes" if _as_bool(payload.get("can_activate")) else "no",
    )
    _append_key_value(
        lines,
        "Safe mode",
        "on" if _as_bool(payload.get("safe_mode")) else "off",
    )

    workspace = _as_dict(payload.get("workspace"))
    if workspace:
        _append_section(lines, "Workspace", colors)
        _append_key_value(
            lines,
            "Status",
            _format_status(workspace.get("status"), colors=colors),
        )
        _append_key_value(lines, "Mode", _as_text(workspace.get("mode")))
        _append_key_value(lines, "Root", _as_text(workspace.get("root")))
        _append_issue_block(lines, _as_list(workspace.get("issues")), colors=colors)

    _append_component_section(
        lines,
        "Providers",
        _as_list(payload.get("providers")),
        kind="provider",
        colors=colors,
        detailed=False,
    )
    _append_component_section(
        lines,
        "Transports",
        _as_list(payload.get("transports")),
        kind="transport",
        colors=colors,
        detailed=False,
    )
    _append_component_section(
        lines,
        "Tools",
        _as_list(payload.get("tools")),
        kind="tool",
        colors=colors,
        detailed=False,
    )

    notices = _as_list(payload.get("notices"))
    if notices:
        _append_section(lines, "Notices", colors)
        for notice in notices:
            _append_line(lines, _as_text(notice))

    issues = _as_list(payload.get("issues"))
    if issues:
        _append_section(lines, "Issues", colors)
        _append_issue_block(lines, issues, colors=colors)

    return "\n".join(lines)


def _render_auth_status(payload: dict[str, object]) -> str:
    colors = _supports_color()
    lines = [_heading("Provider Auth", colors)]

    provider = _as_dict(payload.get("provider"))
    providers = _as_list(payload.get("providers"))
    issues = _as_list(payload.get("issues"))

    if provider:
        _append_section(lines, "Provider", colors)
        for line in _component_lines(provider, kind="provider", colors=colors, detailed=True):
            _append_line(lines, line)
    else:
        _append_component_section(
            lines,
            "Providers",
            providers,
            kind="provider",
            colors=colors,
            detailed=True,
        )

    if issues:
        _append_section(lines, "Issues", colors)
        _append_issue_block(lines, issues, colors=colors)

    return "\n".join(lines)


def _render_update_check(payload: dict[str, object]) -> str:
    colors = _supports_color()
    lines = [_heading("Nagient Update", colors)]

    _append_section(lines, "Summary", colors)
    for line in _update_summary_lines(payload, colors=colors):
        _append_line(lines, line)

    planned = _as_list(payload.get("planned_migrations"))
    if planned:
        _append_section(lines, "Migrations", colors)
        for item in planned:
            migration = _as_dict(item)
            description = _as_text(migration.get("description"))
            command = _as_text(migration.get("command"))
            _append_line(lines, description or _as_text(migration.get("id")))
            if command:
                _append_line(lines, f"Command: {command}", indent="    ")

    return "\n".join(lines)


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    term = os.environ.get("TERM", "")
    if term.lower() == "dumb":
        return False
    return sys.stdout.isatty()


def _paint(text: str, code: str, *, colors: bool) -> str:
    if not colors or not text:
        return text
    return f"\033[{code}m{text}\033[0m"


def _heading(text: str, colors: bool) -> str:
    return _paint(text, "1;36", colors=colors)


def _append_section(lines: list[str], title: str, colors: bool) -> None:
    lines.append("")
    lines.append(_paint(title, "1", colors=colors))


def _append_line(lines: list[str], text: str, *, indent: str = "  ") -> None:
    lines.append(f"{indent}{text}")


def _append_key_value(lines: list[str], label: str, value: str) -> None:
    if value:
        _append_line(lines, f"{label}: {value}")


def _append_issue_block(lines: list[str], issues: list[object], *, colors: bool) -> None:
    for item in issues:
        issue = _as_dict(item)
        message = _as_text(issue.get("message"))
        if not message:
            continue
        severity = _format_status(issue.get("severity"), colors=colors)
        source = _as_text(issue.get("source"))
        prefix = _join_parts(severity, source, separator="  ", wrap_right="()")
        _append_line(lines, _join_parts(prefix, message, separator="  "))
        hint = _as_text(issue.get("hint"))
        if hint:
            _append_line(lines, f"Hint: {hint}", indent="    ")


def _append_component_section(
    lines: list[str],
    title: str,
    items: list[object],
    *,
    kind: str,
    colors: bool,
    detailed: bool,
) -> None:
    _append_section(lines, title, colors)
    if not items:
        _append_line(lines, "No entries.")
        return
    for item in items:
        for line in _component_lines(_as_dict(item), kind=kind, colors=colors, detailed=detailed):
            _append_line(lines, line)


def _component_lines(
    item: dict[str, object],
    *,
    kind: str,
    colors: bool,
    detailed: bool,
) -> list[str]:
    identifier_key = {
        "provider": "provider_id",
        "transport": "transport_id",
        "tool": "tool_id",
    }.get(kind, "id")
    identifier = _as_text(item.get(identifier_key)) or "unknown"
    if kind == "provider" and _as_bool(item.get("default")):
        identifier = f"{identifier} [default]"

    status = _format_status(item.get("status"), colors=colors)
    details: list[str] = []

    plugin_id = _as_text(item.get("plugin_id"))
    if detailed and plugin_id:
        details.append(f"plugin {plugin_id}")

    if kind == "provider":
        model = _as_text(item.get("configured_model"))
        if model:
            details.append(f"model {model}")
        auth_mode = _as_text(item.get("auth_mode"))
        if detailed and auth_mode:
            details.append(f"auth {auth_mode}")
        if _has_value(item.get("authenticated")) and _as_bool(item.get("enabled")):
            details.append(
                "credentials ok" if _as_bool(item.get("authenticated")) else "credentials missing"
            )
        auth_message = _as_text(item.get("auth_message"))
        if detailed and auth_message and _normalized_status(item.get("status")) != "disabled":
            details.append(auth_message)
    elif kind == "transport":
        functions = len(_as_list(item.get("exposed_functions"))) if detailed else 0
        if functions:
            details.append(f"functions {functions}")
    elif kind == "tool":
        functions = len(_as_list(item.get("exposed_functions"))) if detailed else 0
        if functions:
            details.append(f"functions {functions}")

    issue_count = len(_as_list(item.get("issues")))
    if issue_count:
        details.append(f"issues {issue_count}")

    head = _join_parts(identifier, status, separator="  ")
    if details:
        head = _join_parts(head, ", ".join(details), separator="  ")

    lines = [head]
    if detailed and issue_count:
        for issue in _as_list(item.get("issues")):
            issue_payload = _as_dict(issue)
            message = _as_text(issue_payload.get("message"))
            if message:
                lines.append(f"  - {message}")
            hint = _as_text(issue_payload.get("hint"))
            if hint:
                lines.append(f"    hint: {hint}")
    return lines


def _update_summary_lines(payload: dict[str, object], *, colors: bool) -> list[str]:
    status = _normalized_status(payload.get("status"))
    update_available = payload.get("update_available")

    if _has_value(update_available) and _as_bool(update_available):
        current_version = _as_text(payload.get("current_version"))
        target_version = _as_text(payload.get("target_version"))
        return [
            _join_parts(
                "Status:",
                _format_status("update_available", colors=colors),
                separator=" ",
            ),
            f"Current: {current_version}",
            f"Target: {target_version}",
        ]
    if _has_value(update_available) and not _as_bool(update_available):
        version = _as_text(payload.get("current_version")) or _as_text(
            payload.get("target_version")
        )
        if version:
            return [f"Up to date: {version}"]
        return ["Up to date."]
    if status == "ready":
        version = _as_text(payload.get("current_version")) or _as_text(
            payload.get("target_version")
        )
        if version:
            return [f"Up to date: {version}"]
        return ["Up to date."]
    if status == "skipped":
        return ["Not configured."]

    message = _as_text(payload.get("message")) or "Status unavailable."
    return [
        _join_parts(
            "Status:",
            _format_status(payload.get("status"), colors=colors),
            separator=" ",
        ),
        message,
    ]


def _agent_readiness_lines(activation: dict[str, object]) -> list[str]:
    providers = _as_list(activation.get("providers"))
    if not providers:
        return ["Runtime is up, but provider status is not available yet."]

    enabled_providers = [
        provider for provider in providers if _as_bool(_as_dict(provider).get("enabled"))
    ]
    if not enabled_providers:
        return [
            "Runtime is running, but the agent is not configured yet.",
            "No provider profile is enabled, so model requests cannot run.",
        ]

    authenticated_providers = [
        provider
        for provider in enabled_providers
        if _as_bool(_as_dict(provider).get("authenticated"))
        or _as_text(_as_dict(provider).get("auth_mode")) == "none"
    ]
    if not authenticated_providers:
        return [
            "Runtime is running, but enabled providers are missing usable credentials.",
            "Complete provider auth before running full agent workflows.",
        ]

    return []


def _next_steps(payload: dict[str, object]) -> list[str]:
    steps: list[str] = []
    activation = _as_dict(payload.get("activation"))
    providers = _as_list(activation.get("providers"))
    enabled_providers = [item for item in providers if _as_bool(_as_dict(item).get("enabled"))]
    authenticated_providers = [
        item
        for item in enabled_providers
        if _as_bool(_as_dict(item).get("authenticated"))
        or _as_text(_as_dict(item).get("auth_mode")) == "none"
    ]

    host_paths = _host_paths()
    config_path = "@config"
    secrets_path = "@secrets"

    if not activation:
        steps.append("Run `nagient reconcile` to generate the activation report.")

    if not enabled_providers:
        steps.append(f"Enable a provider profile in `{config_path}`.")
        steps.append(f"Add the matching secret to `{secrets_path}`.")
        steps.append("Run `nagient auth status` to verify the provider setup.")
    elif not authenticated_providers:
        steps.append("Run `nagient auth status` to see which provider still needs credentials.")
        steps.append("Use `nagient auth login <provider_id>` after adding the secret.")

    workspace = _as_dict(payload.get("workspace"))
    if _normalized_status(workspace.get("status")) not in {"", "ready"}:
        steps.append("Fix the workspace issue, then run `nagient reconcile` again.")

    if activation and not _as_bool(activation.get("can_activate")):
        steps.append("Review the issues above and rerun `nagient reconcile`.")

    return steps[:3]


def _host_paths() -> dict[str, str]:
    home = os.environ.get("NAGIENT_HOST_HOME", "").strip()
    if not home:
        return {}

    def _env_or_default(name: str, suffix: str) -> str:
        value = os.environ.get(name, "").strip()
        if value:
            return value
        return str(Path(home) / suffix)

    return {
        "home": home,
        "config": _env_or_default("NAGIENT_HOST_CONFIG_FILE", "config.toml"),
        "secrets": _env_or_default("NAGIENT_HOST_SECRETS_FILE", "secrets.env"),
        "tool_secrets": _env_or_default(
            "NAGIENT_HOST_TOOL_SECRETS_FILE",
            "tool-secrets.env",
        ),
        "workspace": _env_or_default("NAGIENT_HOST_WORKSPACE_DIR", "workspace"),
    }


def _format_status(value: object, *, colors: bool) -> str:
    status = _normalized_status(value).replace("_", " ") or "unknown"
    color_code = {
        "ready": "32",
        "healthy": "32",
        "update available": "33",
        "degraded": "33",
        "warning": "33",
        "failed": "31",
        "blocked": "31",
        "error": "31",
        "disabled": "90",
        "skipped": "90",
        "unavailable": "33",
        "unauthenticated": "33",
        "update_available": "33",
    }.get(status, "36")
    return _paint(status, color_code, colors=colors)


def _normalized_status(value: object) -> str:
    return _as_text(value).strip().lower()


def _as_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _as_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _as_bool(value: object) -> bool:
    return bool(value)


def _as_int(value: object) -> int:
    return int(value) if isinstance(value, int) else 0


def _has_value(value: object) -> bool:
    return value is not None and value != ""


def _join_parts(
    left: str,
    right: str,
    *,
    separator: str,
    wrap_right: str | None = None,
) -> str:
    if not left:
        return right
    if not right:
        return left
    if wrap_right == "()":
        return f"{left}{separator}({right})"
    return f"{left}{separator}{right}"
