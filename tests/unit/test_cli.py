from __future__ import annotations

import io
import json
import os
import runpy
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from nagient import cli


class _Serializable:
    def __init__(self, payload: dict[str, object], **attrs: object) -> None:
        self._payload = payload
        for key, value in attrs.items():
            setattr(self, key, value)

    def to_dict(self) -> dict[str, object]:
        return self._payload


def _issue(
    severity: str,
    message: str,
    *,
    source: str = "system",
    hint: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "severity": severity,
        "message": message,
        "source": source,
    }
    if hint is not None:
        payload["hint"] = hint
    return payload


def _plugin(
    *,
    plugin_id: str,
    display_name: str,
    namespace: str = "builtin",
    family: str = "builtin",
) -> SimpleNamespace:
    manifest = SimpleNamespace(
        plugin_id=plugin_id,
        display_name=display_name,
        namespace=namespace,
        family=family,
        required_config=["token"],
        optional_config=["model"],
        custom_functions=["custom.echo"],
        exposed_functions=["echo.run"],
        supported_auth_modes=["api_key"],
        default_auth_mode="api_key",
        capabilities=["list_models"],
        secret_config=["api_key_secret"],
    )
    return SimpleNamespace(manifest=manifest, source="builtin")


def _discovery(*plugins: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        plugins={plugin.manifest.plugin_id: plugin for plugin in plugins},
        issues=[_Serializable(_issue("warning", "discovery warning"))],
    )


def _status_payload(update: dict[str, object]) -> dict[str, object]:
    return {
        "service": "nagient",
        "version": "1.2.3",
        "channel": "stable",
        "update_base_url": "https://updates.test",
        "safe_mode": True,
        "paths": {
            "home": "/opt/nagient",
            "config": "/opt/nagient/config.toml",
            "secrets": "/opt/nagient/secrets.env",
            "tool_secrets": "/opt/nagient/tool-secrets.env",
            "plugins": "/opt/nagient/plugins",
            "tools": "/opt/nagient/tools",
            "providers": "/opt/nagient/providers",
            "credentials": "/opt/nagient/credentials",
            "state": "/opt/nagient/state",
            "logs": "/opt/nagient/logs",
            "releases": "/opt/nagient/releases",
        },
        "workspace": {
            "workspace_id": "workspace-1",
            "root": "/workspace",
            "mode": "bounded",
            "nagient_dir": "/workspace/.nagient",
            "status": "degraded",
            "backup_enabled": True,
            "issues": [
                _issue(
                    "warning",
                    "Workspace index is stale.",
                    source="workspace",
                    hint="Run reconcile.",
                )
            ],
        },
        "secrets": {"core_count": 1, "tool_count": 2},
        "pending_workflows": {"interactions": 1, "approvals": 2},
        "activation": {
            "status": "degraded",
            "safe_mode": True,
            "can_activate": False,
            "providers": [
                {
                    "provider_id": "openai",
                    "plugin_id": "builtin.openai",
                    "enabled": True,
                    "default": True,
                    "status": "unauthenticated",
                    "authenticated": False,
                    "auth_mode": "api_key",
                    "auth_message": "Missing API key.",
                    "configured_model": "gpt-4.1-mini",
                    "issues": [
                        _issue(
                            "warning",
                            "Provider missing credentials.",
                            source="openai",
                            hint="Run auth login.",
                        )
                    ],
                }
            ],
            "transports": [
                {
                    "transport_id": "console",
                    "plugin_id": "builtin.console",
                    "enabled": True,
                    "status": "ready",
                    "exposed_functions": ["console.start", "console.stop"],
                    "issues": [],
                },
                {
                    "transport_id": "telegram",
                    "plugin_id": "builtin.telegram",
                    "enabled": False,
                    "status": "disabled",
                    "exposed_functions": [],
                    "issues": [],
                },
            ],
            "tools": [
                {
                    "tool_id": "workspace_fs",
                    "plugin_id": "workspace.fs",
                    "enabled": True,
                    "status": "ready",
                    "exposed_functions": ["workspace.fs.read_text"],
                    "issues": [],
                },
                {
                    "tool_id": "system_reconcile",
                    "plugin_id": "system.reconcile",
                    "enabled": True,
                    "status": "failed",
                    "exposed_functions": ["system.reconcile.run"],
                    "issues": [_issue("error", "Tool crashed.", source="tool")],
                },
            ],
            "workspace": {
                "workspace_id": "workspace-1",
                "root": "/workspace",
                "mode": "bounded",
                "nagient_dir": "/workspace/.nagient",
                "status": "degraded",
                "backup_enabled": True,
                "issues": [_issue("warning", "Activation workspace issue.")],
            },
            "issues": [
                _issue(
                    "error",
                    "Runtime activation blocked.",
                    hint="Review provider credentials.",
                )
            ],
            "notices": ["Runtime activation status: degraded."],
        },
        "effective_config": {
            "default_provider": "openai",
            "require_provider": True,
            "settings": {"heartbeat_interval_seconds": "30"},
        },
        "update": update,
    }


def _run_main(argv: list[str], *, container: SimpleNamespace) -> tuple[int, str]:
    stdout = io.StringIO()
    with patch("nagient.cli.build_container", return_value=container):
        with redirect_stdout(stdout):
            exit_code = cli.main(argv)
    return exit_code, stdout.getvalue()


class CliTests(unittest.TestCase):
    def test_render_text_views_are_structured(self) -> None:
        payload = _status_payload(
            {
                "status": "ready",
                "current_version": "1.2.3",
                "target_version": "1.2.4",
                "update_available": True,
                "message": "Update available.",
            }
        )
        with patch.dict(
            os.environ,
            {
                "NAGIENT_HOST_HOME": "/host/.nagient",
                "NAGIENT_HOST_CONFIG_FILE": "/host/.nagient/config.toml",
                "NAGIENT_HOST_SECRETS_FILE": "/host/.nagient/secrets.env",
                "NAGIENT_HOST_TOOL_SECRETS_FILE": "/host/.nagient/tool-secrets.env",
                "NAGIENT_HOST_WORKSPACE_DIR": "/host/.nagient/workspace",
                "NO_COLOR": "1",
            },
            clear=False,
        ):
            status_text = cli._render_text(payload, view="status", verbose=False)
            doctor_text = cli._render_text(payload, view="doctor", verbose=False)
            auth_text = cli._render_text(
                {"provider": payload["activation"]["providers"][0], "issues": []},
                view="auth_status",
                verbose=False,
            )
            update_text = cli._render_text(
                {
                    "status": "ready",
                    "current_version": "1.2.3",
                    "target_version": "1.2.4",
                    "update_available": True,
                    "planned_migrations": [
                        {
                            "id": "sync-state",
                            "description": "Sync runtime state.",
                            "command": "nagient migrations sync-state",
                        }
                    ],
                },
                view="update_check",
                verbose=False,
            )

        self.assertIn("Nagient Status", status_text)
        self.assertIn("Overview", status_text)
        self.assertIn("@config: /host/.nagient/config.toml", status_text)
        self.assertIn("Status: update available", status_text)
        self.assertIn("Next Steps", status_text)
        self.assertIn("nagient auth login <provider_id>", status_text)

        self.assertIn("Nagient Doctor", doctor_text)
        self.assertIn("Runtime Files", doctor_text)
        self.assertIn("Default provider: openai", doctor_text)
        self.assertIn("Provider missing credentials.", doctor_text)

        self.assertIn("Provider Auth", auth_text)
        self.assertIn("openai [default]", auth_text)
        self.assertIn("credentials missing", auth_text)

        self.assertIn("Nagient Update", update_text)
        self.assertIn("Sync runtime state.", update_text)
        self.assertIn("Command: nagient migrations sync-state", update_text)

    def test_render_text_verbose_and_generic_paths(self) -> None:
        payload = {
            "alpha": {"beta": 1},
            "items": [{"name": "first"}, "second"],
        }

        verbose_text = cli._render_text(payload, view="status", verbose=True)
        generic_text = cli._render_text(payload, view="generic", verbose=False)

        self.assertIn("alpha.beta: 1", verbose_text)
        self.assertIn("items:", verbose_text)
        self.assertIn("  - second", verbose_text)
        self.assertEqual(verbose_text, generic_text)

    def test_misc_cli_helpers(self) -> None:
        manifest = cli._build_release_manifest_payload(
            version="9.9.9",
            channel="stable",
            base_url="https://updates.test",
            docker_image="docker.io/acme/nagient:9.9.9",
            published_at="2026-01-01T00:00:00Z",
            summary="Test release.",
        )

        self.assertEqual(manifest["version"], "9.9.9")
        self.assertEqual(manifest["docker"]["compose_url"], "https://updates.test/9.9.9/docker-compose.yml")
        self.assertEqual(manifest["artifacts"][0]["name"], "install.sh")

        self.assertEqual(cli._load_json_argument('{"ok": true}'), {"ok": True})
        with self.assertRaises(ValueError):
            cli._load_json_argument('["not-an-object"]')

        with patch("getpass.getpass", return_value=" secret-value "):
            self.assertEqual(cli._read_secret_input("prompt"), "secret-value")
        with patch("getpass.getpass", side_effect=KeyboardInterrupt):
            self.assertIsNone(cli._read_secret_input("prompt"))

        self.assertEqual(
            cli._parse_assignment_pairs(["enabled=true", "port=8080", 'meta={"ok":true}']),
            {"enabled": True, "port": 8080, "meta": {"ok": True}},
        )
        self.assertEqual(cli._coerce_cli_value("null"), None)
        self.assertEqual(cli._coerce_cli_value("plain-text"), "plain-text")
        self.assertTrue(cli._resolve_enablement(True, False))
        self.assertFalse(cli._resolve_enablement(False, True))
        self.assertIsNone(cli._resolve_enablement(False, False))
        self.assertTrue(cli._resolve_default_flag(True, False))
        self.assertFalse(cli._resolve_default_flag(False, True))
        self.assertIsNone(cli._resolve_default_flag(False, False))
        with self.assertRaises(ValueError):
            cli._resolve_enablement(True, True)
        with self.assertRaises(ValueError):
            cli._resolve_default_flag(True, True)
        settings = SimpleNamespace(
            home_dir=Path("/tmp/nagient"),
            config_file=Path("/tmp/nagient/config.toml"),
            secrets_file=Path("/tmp/nagient/secrets.env"),
            tool_secrets_file=Path("/tmp/nagient/tool-secrets.env"),
            plugins_dir=Path("/tmp/nagient/plugins"),
            providers_dir=Path("/tmp/nagient/providers"),
            tools_dir=Path("/tmp/nagient/tools"),
            credentials_dir=Path("/tmp/nagient/credentials"),
            state_dir=Path("/tmp/nagient/state"),
            log_dir=Path("/tmp/nagient/logs"),
            releases_dir=Path("/tmp/nagient/releases"),
        )
        self.assertEqual(
            cli._resolve_path_alias("@home/cache", settings),
            "/tmp/nagient/cache",
        )
        self.assertEqual(
            cli._render_path_value("/tmp/nagient/plugins/custom", settings),
            "@plugins/custom",
        )

    def test_prompt_for_model_selection(self) -> None:
        models = [
            {"model_id": "gpt-5", "display_name": "GPT-5"},
            {"model_id": "gpt-5-mini", "display_name": "GPT-5 Mini"},
        ]
        with patch("builtins.input", return_value="2"):
            self.assertEqual(cli._prompt_for_model_selection(models), "gpt-5-mini")
        with patch("builtins.input", return_value="0"):
            self.assertIsNone(cli._prompt_for_model_selection(models))
        with patch("builtins.input", return_value=""):
            self.assertIsNone(cli._prompt_for_model_selection(models))
        with patch("builtins.input", return_value="oops"):
            with self.assertRaises(ValueError):
                cli._prompt_for_model_selection(models)

    def test_interactive_chat_session_exits_cleanly(self) -> None:
        container = SimpleNamespace(
            provider_service=SimpleNamespace(
                chat=Mock(return_value={"message": "hello", "provider_id": "openai"})
            )
        )
        with patch("builtins.input", side_effect=["hey", "0"]):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = cli._run_chat_session(
                    container,
                    provider_id="openai",
                    system_prompt=None,
                )
        self.assertEqual(exit_code, 0)
        self.assertIn("assistant> hello", stdout.getvalue())

    def test_main_routes_core_and_extended_commands(self) -> None:
        status_payload = _status_payload(
            {
                "status": "ready",
                "current_version": "1.2.3",
                "target_version": "1.2.3",
                "update_available": False,
                "message": "Already current.",
            }
        )
        preflight_payload = {
            "status": "ready",
            "can_activate": True,
            "safe_mode": True,
            "providers": [],
            "transports": [],
            "tools": [],
            "workspace": {
                "status": "ready",
                "mode": "bounded",
                "root": "/workspace",
                "issues": [],
            },
            "issues": [],
            "notices": ["Preflight ok."],
        }
        reconcile_payload = dict(preflight_payload)
        reconcile_payload["status"] = "blocked"
        reconcile_payload["can_activate"] = False
        reconcile_payload["issues"] = [_issue("error", "Blocked.")]

        transport_plugin = _plugin(
            plugin_id="builtin.console",
            display_name="Console",
            namespace="builtin.console",
        )
        provider_plugin = _plugin(
            plugin_id="builtin.openai",
            display_name="OpenAI",
            family="openai",
        )
        update_step = SimpleNamespace(
            step_id="sync-state",
            from_version="1.2.3",
            to_version="1.2.4",
            description="Sync state.",
            command="nagient migrations sync-state",
        )
        update_notice = SimpleNamespace(
            current_version="1.2.3",
            target_version="1.2.4",
            update_available=True,
            message="Update available.",
            manifest=None,
            planned_migrations=[update_step],
        )
        container = SimpleNamespace(
            settings=SimpleNamespace(
                home_dir=Path("/tmp/nagient"),
                config_file=Path("/tmp/nagient/config.toml"),
                secrets_file=Path("/tmp/nagient/secrets.env"),
                tool_secrets_file=Path("/tmp/nagient/tool-secrets.env"),
                plugins_dir=Path("/tmp/nagient/plugins"),
                providers_dir=Path("/tmp/nagient/providers"),
                tools_dir=Path("/tmp/nagient/tools"),
                credentials_dir=Path("/tmp/nagient/credentials"),
                state_dir=Path("/tmp/nagient/state"),
                log_dir=Path("/tmp/nagient/logs"),
                releases_dir=Path("/tmp/nagient/releases"),
            ),
            configuration_service=SimpleNamespace(
                initialize=Mock(return_value={"written_files": ["config.toml"]}),
                scaffold_transport=Mock(
                    return_value=_Serializable({"plugin_id": "custom.echo"})
                ),
                scaffold_provider=Mock(
                    return_value=_Serializable({"plugin_id": "custom.provider"})
                ),
                scaffold_tool=Mock(return_value=_Serializable({"plugin_id": "custom.tool"})),
                configure_provider=Mock(
                    side_effect=[
                        {
                            "component": "provider",
                            "provider_id": "openai",
                            "plugin_id": "builtin.openai",
                            "enabled": True,
                            "default": True,
                            "config": {"model": "gpt-4.1-mini"},
                        },
                        {
                            "component": "provider",
                            "provider_id": "openai",
                            "plugin_id": "builtin.openai",
                            "enabled": True,
                            "default": True,
                            "config": {"model": "gpt-4.1"},
                        },
                        {
                            "component": "provider",
                            "provider_id": "openai",
                            "plugin_id": "builtin.openai",
                            "enabled": True,
                            "default": True,
                            "config": {"model": "gpt-4.1"},
                        },
                    ]
                ),
                configure_transport=Mock(
                    return_value={
                        "component": "transport",
                        "transport_id": "webhook",
                        "plugin_id": "builtin.webhook",
                        "enabled": True,
                    }
                ),
                configure_tool=Mock(
                    return_value={
                        "component": "tool",
                        "tool_id": "workspace_fs",
                        "plugin_id": "workspace.fs",
                        "enabled": True,
                    }
                ),
                configure_workspace=Mock(
                    return_value={
                        "component": "workspace",
                        "workspace": {"root": "/tmp/workspace", "mode": "unsafe"},
                    }
                ),
                configure_paths=Mock(
                    return_value={
                        "component": "paths",
                        "paths": {"secrets_file": "/tmp/secrets.env"},
                    }
                ),
                select_provider_model=Mock(
                    return_value={
                        "provider_id": "openai",
                        "models": [
                            {"model_id": "gpt-4.1-mini", "display_name": "GPT Mini"},
                            {"model_id": "gpt-4.1", "display_name": "GPT"},
                        ],
                    }
                ),
            ),
            status_service=SimpleNamespace(collect=Mock(return_value=status_payload)),
            preflight_service=SimpleNamespace(
                inspect=Mock(return_value=_Serializable(preflight_payload))
            ),
            reconcile_service=SimpleNamespace(
                reconcile=Mock(
                    return_value=_Serializable(
                        reconcile_payload,
                        can_activate=False,
                    )
                )
            ),
            runtime_agent=SimpleNamespace(serve=Mock(return_value=7)),
            plugin_registry=SimpleNamespace(discover=Mock(return_value=_discovery(transport_plugin))),
            provider_registry=SimpleNamespace(
                discover=Mock(return_value=_discovery(provider_plugin))
            ),
            provider_service=SimpleNamespace(
                list_models=Mock(
                    return_value={
                        "provider_id": "openai",
                        "plugin_id": "builtin.openai",
                        "models": [{"model_id": "gpt-4.1-mini", "display_name": "GPT"}],
                    }
                ),
                auth_status=Mock(
                    return_value={
                        "provider": {
                            "provider_id": "openai",
                            "plugin_id": "builtin.openai",
                            "enabled": True,
                            "default": True,
                            "status": "ready",
                            "authenticated": True,
                            "auth_mode": "api_key",
                            "auth_message": "Ready.",
                            "configured_model": "gpt-4.1-mini",
                            "issues": [],
                        },
                        "issues": [],
                    }
                ),
                login=Mock(return_value={"provider": {"provider_id": "openai"}}),
                complete_login=Mock(return_value={"provider": {"provider_id": "openai"}}),
                logout=Mock(return_value={"provider": {"provider_id": "openai"}}),
                chat=Mock(
                    return_value={
                        "provider_id": "openai",
                        "plugin_id": "builtin.openai",
                        "model": "gpt-4.1-mini",
                        "transport_id": "console",
                        "message": "hello from provider",
                    }
                ),
            ),
            tool_service=SimpleNamespace(
                list_tools=Mock(return_value={"tools": [{"tool_id": "workspace_fs"}]}),
                invoke=Mock(
                    return_value=_Serializable({"tool_id": "workspace_fs", "status": "success"})
                ),
            ),
            update_service=SimpleNamespace(check=Mock(return_value=update_notice)),
            workflow_service=SimpleNamespace(
                list_interactions=Mock(return_value=[_Serializable({"request_id": "i1"})]),
                submit_interaction=Mock(
                    return_value=_Serializable({"request_id": "i1", "status": "success"})
                ),
                list_approvals=Mock(return_value=[_Serializable({"request_id": "a1"})]),
                resolve_approval=Mock(
                    return_value=_Serializable({"request_id": "a1", "status": "approved"})
                ),
            ),
            agent_turn_service=SimpleNamespace(
                run_turn=Mock(
                    return_value=_Serializable(
                        {
                            "tool_results": [],
                            "interaction_requests": [],
                            "approval_requests": [],
                        }
                    )
                )
            ),
        )

        exit_code, output = _run_main(["version"], container=container)
        self.assertEqual(exit_code, 0)
        self.assertIn(cli.__version__, output)

        exit_code, output = _run_main(["init", "--format", "json"], container=container)
        self.assertEqual(exit_code, 0)
        self.assertIn('"written_files"', output)

        exit_code, output = _run_main(["status"], container=container)
        self.assertEqual(exit_code, 0)
        self.assertIn("Nagient Status", output)

        exit_code, output = _run_main(["paths"], container=container)
        self.assertEqual(exit_code, 0)
        self.assertIn("Nagient Paths", output)
        self.assertIn("@config", output)

        exit_code, output = _run_main(["doctor", "--verbose"], container=container)
        self.assertEqual(exit_code, 0)
        self.assertIn("effective_config.default_provider: openai", output)

        exit_code, output = _run_main(["preflight"], container=container)
        self.assertEqual(exit_code, 0)
        self.assertIn("Nagient Preflight", output)

        exit_code, output = _run_main(["reconcile"], container=container)
        self.assertEqual(exit_code, 1)
        self.assertIn("Nagient Reconcile", output)

        exit_code, _ = _run_main(["serve", "--once"], container=container)
        self.assertEqual(exit_code, 7)

        exit_code, output = _run_main(
            [
                "setup",
                "provider",
                "openai",
                "--enable",
                "--default",
                "--auth",
                "api_key",
                "--secret-name",
                "OPENAI_API_KEY",
                "--model",
                "gpt-4.1-mini",
                "--set",
                "temperature=0.2",
                "--format",
                "json",
            ],
            container=container,
        )
        self.assertEqual(exit_code, 0)
        self.assertIn('"provider_id": "openai"', output)
        container.configuration_service.configure_provider.assert_any_call(
            "openai",
            plugin_id=None,
            enabled=True,
            default=True,
            config_updates={
                "auth": "api_key",
                "api_key_secret": "OPENAI_API_KEY",
                "model": "gpt-4.1-mini",
                "temperature": 0.2,
            },
        )

        with patch("builtins.input", return_value="2"):
            exit_code, output = _run_main(
                [
                    "setup",
                    "provider",
                    "openai",
                    "--select-model",
                    "--format",
                    "json",
                ],
                container=container,
            )
        self.assertEqual(exit_code, 0)
        self.assertIn('"selected_model": "gpt-4.1"', output)
        container.configuration_service.select_provider_model.assert_called_with("openai")

        exit_code, output = _run_main(
            [
                "setup",
                "transport",
                "webhook",
                "--enable",
                "--set",
                "listen_port=8081",
                "--format",
                "json",
            ],
            container=container,
        )
        self.assertEqual(exit_code, 0)
        self.assertIn('"transport_id": "webhook"', output)

        exit_code, output = _run_main(
            [
                "setup",
                "tool",
                "workspace_fs",
                "--enable",
                "--format",
                "json",
            ],
            container=container,
        )
        self.assertEqual(exit_code, 0)
        self.assertIn('"tool_id": "workspace_fs"', output)

        exit_code, output = _run_main(
            [
                "setup",
                "workspace",
                "--root",
                "/tmp/workspace",
                "--mode",
                "unsafe",
                "--format",
                "json",
            ],
            container=container,
        )
        self.assertEqual(exit_code, 0)
        self.assertIn('"component": "workspace"', output)

        exit_code, output = _run_main(
            [
                "setup",
                "paths",
                "--secrets-file",
                "/tmp/secrets.env",
                "--format",
                "json",
            ],
            container=container,
        )
        self.assertEqual(exit_code, 0)
        self.assertIn('"component": "paths"', output)

        exit_code, output = _run_main(
            ["transport", "list", "--format", "json"],
            container=container,
        )
        self.assertEqual(exit_code, 0)
        self.assertIn('"plugin_id": "builtin.console"', output)

        exit_code, output = _run_main(
            ["transport", "scaffold", "--plugin-id", "custom.echo", "--format", "json"],
            container=container,
        )
        self.assertEqual(exit_code, 0)
        self.assertIn('"plugin_id": "custom.echo"', output)

        exit_code, output = _run_main(
            ["provider", "list", "--format", "json"],
            container=container,
        )
        self.assertEqual(exit_code, 0)
        self.assertIn('"plugin_id": "builtin.openai"', output)

        exit_code, output = _run_main(
            ["provider", "scaffold", "--plugin-id", "custom.provider", "--format", "json"],
            container=container,
        )
        self.assertEqual(exit_code, 0)
        self.assertIn('"plugin_id": "custom.provider"', output)

        exit_code, output = _run_main(
            ["provider", "models", "openai", "--format", "json"],
            container=container,
        )
        self.assertEqual(exit_code, 0)
        self.assertIn('"models"', output)

        exit_code, output = _run_main(
            ["chat", "hello", "--format", "json"],
            container=container,
        )
        self.assertEqual(exit_code, 0)
        self.assertIn('"message": "hello from provider"', output)

        exit_code, output = _run_main(
            ["tool", "list", "--format", "json"],
            container=container,
        )
        self.assertEqual(exit_code, 0)
        self.assertIn('"tool_id": "workspace_fs"', output)

        exit_code, output = _run_main(
            ["tool", "scaffold", "--plugin-id", "custom.tool", "--format", "json"],
            container=container,
        )
        self.assertEqual(exit_code, 0)
        self.assertIn('"plugin_id": "custom.tool"', output)

        exit_code, output = _run_main(
            [
                "tool",
                "invoke",
                "workspace.fs.read_text",
                "--tool-id",
                "workspace_fs",
                "--args-json",
                '{"path": "README.md"}',
                "--format",
                "json",
            ],
            container=container,
        )
        self.assertEqual(exit_code, 0)
        self.assertIn('"status": "success"', output)

        exit_code, output = _run_main(
            ["auth", "status", "openai"],
            container=container,
        )
        self.assertEqual(exit_code, 0)
        self.assertIn("Provider Auth", output)

        for argv in (
            [
                "auth",
                "login",
                "openai",
                "--api-key",
                "sk-test",
                "--format",
                "json",
            ],
            [
                "auth",
                "complete",
                "openai",
                "--session-id",
                "session-1",
                "--format",
                "json",
            ],
            ["auth", "logout", "openai", "--format", "json"],
        ):
            exit_code, output = _run_main(argv, container=container)
            self.assertEqual(exit_code, 0)
            self.assertIn('"provider"', output)

        exit_code, output = _run_main(
            [
                "update",
                "check",
                "--current-version",
                "1.2.3",
                "--channel",
                "stable",
            ],
            container=container,
        )
        self.assertEqual(exit_code, 0)
        self.assertIn("Nagient Update", output)

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            request_path = Path(temp_dir) / "agent-turn.json"
            request_path.write_text(json.dumps({"messages": []}), encoding="utf-8")

            exit_code, output = _run_main(
                [
                    "manifest",
                    "render",
                    "--version",
                    "9.9.9",
                    "--channel",
                    "stable",
                    "--base-url",
                    "https://updates.test",
                    "--docker-image",
                    "docker.io/acme/nagient:9.9.9",
                    "--output",
                    str(manifest_path),
                ],
                container=container,
            )
            self.assertEqual(exit_code, 0)
            self.assertTrue(manifest_path.exists())
            self.assertIn('"version": "9.9.9"', output)

            exit_code, output = _run_main(
                [
                    "migrations",
                    "plan",
                    "--manifest-ref",
                    "tests/fixtures/update_center/manifests/0.2.0.json",
                    "--current-version",
                    "1.2.3",
                    "--format",
                    "json",
                ],
                container=container,
            )
            self.assertEqual(exit_code, 0)
            self.assertIn('"planned_migrations"', output)

            exit_code, output = _run_main(
                ["interaction", "list", "--format", "json"],
                container=container,
            )
            self.assertEqual(exit_code, 0)
            self.assertIn('"request_id": "i1"', output)

            exit_code, output = _run_main(
                [
                    "interaction",
                    "submit",
                    "i1",
                    "--response",
                    "done",
                    "--format",
                    "json",
                ],
                container=container,
            )
            self.assertEqual(exit_code, 0)
            self.assertIn('"status": "success"', output)

            exit_code, output = _run_main(
                ["approval", "list", "--format", "json"],
                container=container,
            )
            self.assertEqual(exit_code, 0)
            self.assertIn('"request_id": "a1"', output)

            exit_code, output = _run_main(
                [
                    "approval",
                    "respond",
                    "a1",
                    "--decision",
                    "approve",
                    "--format",
                    "json",
                ],
                container=container,
            )
            self.assertEqual(exit_code, 0)
            self.assertIn('"status": "approved"', output)

            exit_code, output = _run_main(
                [
                    "agent",
                    "turn",
                    "--request-file",
                    str(request_path),
                    "--format",
                    "json",
                ],
                container=container,
            )
            self.assertEqual(exit_code, 0)
            self.assertIn('"tool_results"', output)

    def test_module_entrypoint_raises_system_exit(self) -> None:
        with patch("nagient.cli.main", return_value=3):
            with self.assertRaises(SystemExit) as context:
                runpy.run_module("nagient.__main__", run_name="__main__")

        self.assertEqual(context.exception.code, 3)


if __name__ == "__main__":
    unittest.main()
