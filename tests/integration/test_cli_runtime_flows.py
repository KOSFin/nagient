from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.bootstrap import PROJECT_ROOT, SRC_ROOT


class CliRuntimeFlowsTests(unittest.TestCase):
    def test_init_preflight_scaffold_and_transport_list_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            env = {
                **os.environ,
                "PYTHONPATH": str(SRC_ROOT),
                "NAGIENT_HOME": str(home_dir),
            }

            init_process = subprocess.run(
                [sys.executable, "-m", "nagient", "init", "--format", "json"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            init_payload = json.loads(init_process.stdout)
            self.assertTrue((home_dir / "config.toml").exists())
            self.assertTrue((home_dir / "secrets.env").exists())
            self.assertTrue((home_dir / "providers" / "README.md").exists())
            self.assertIn(str((home_dir / "config.toml").resolve()), init_payload["written_files"])

            preflight_process = subprocess.run(
                [sys.executable, "-m", "nagient", "preflight", "--format", "json"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            preflight_payload = json.loads(preflight_process.stdout)
            self.assertEqual(preflight_payload["status"], "ready")
            self.assertTrue(preflight_payload["can_activate"])

            scaffold_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nagient",
                    "transport",
                    "scaffold",
                    "--plugin-id",
                    "custom.echo",
                    "--format",
                    "json",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            scaffold_payload = json.loads(scaffold_process.stdout)
            plugin_dir = home_dir / "plugins" / "custom.echo"
            self.assertEqual(scaffold_payload["plugin_id"], "custom.echo")
            self.assertTrue((plugin_dir / "plugin.toml").exists())
            scaffold_manifest = (plugin_dir / "plugin.toml").read_text(encoding="utf-8")
            self.assertIn('poll_inbound_events = "echo.pollInboundEvents"', scaffold_manifest)

            transport_list_process = subprocess.run(
                [sys.executable, "-m", "nagient", "transport", "list", "--format", "json"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            list_payload = json.loads(transport_list_process.stdout)
            plugin_ids = {item["plugin_id"] for item in list_payload["plugins"]}
            self.assertIn("builtin.console", plugin_ids)
            self.assertIn("custom.echo", plugin_ids)

            provider_scaffold_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nagient",
                    "provider",
                    "scaffold",
                    "--plugin-id",
                    "custom.provider",
                    "--format",
                    "json",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            provider_scaffold_payload = json.loads(provider_scaffold_process.stdout)
            provider_dir = home_dir / "providers" / "custom.provider"
            self.assertEqual(provider_scaffold_payload["plugin_id"], "custom.provider")
            self.assertTrue((provider_dir / "provider.toml").exists())

            provider_list_process = subprocess.run(
                [sys.executable, "-m", "nagient", "provider", "list", "--format", "json"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            provider_list_payload = json.loads(provider_list_process.stdout)
            provider_plugin_ids = {item["plugin_id"] for item in provider_list_payload["plugins"]}
            self.assertIn("builtin.openai", provider_plugin_ids)
            self.assertIn("custom.provider", provider_plugin_ids)

    def test_reconcile_and_serve_once_write_activation_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            env = {
                **os.environ,
                "PYTHONPATH": str(SRC_ROOT),
                "NAGIENT_HOME": str(home_dir),
            }
            subprocess.run(
                [sys.executable, "-m", "nagient", "init", "--format", "json"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            reconcile_process = subprocess.run(
                [sys.executable, "-m", "nagient", "reconcile", "--format", "json"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            reconcile_payload = json.loads(reconcile_process.stdout)
            self.assertEqual(reconcile_payload["status"], "ready")
            self.assertTrue((home_dir / "state" / "activation-report.json").exists())

            subprocess.run(
                [sys.executable, "-m", "nagient", "serve", "--once"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            heartbeat = json.loads(
                (home_dir / "state" / "heartbeat.json").read_text(encoding="utf-8")
            )
            self.assertEqual(heartbeat["runtime_status"], "ready")
            self.assertEqual(heartbeat["transports"][0]["plugin_id"], "builtin.console")

    def test_transport_test_reports_builtin_telegram_ready_when_token_is_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            env = {
                **os.environ,
                "PYTHONPATH": str(SRC_ROOT),
                "NAGIENT_HOME": str(home_dir),
            }
            subprocess.run(
                [sys.executable, "-m", "nagient", "init", "--format", "json"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            config_file = home_dir / "config.toml"
            config_file.write_text(
                config_file.read_text(encoding="utf-8").replace(
                    "[transports.telegram]\nplugin = \"builtin.telegram\"\nenabled = false",
                    "[transports.telegram]\nplugin = \"builtin.telegram\"\nenabled = true",
                ),
                encoding="utf-8",
            )
            (home_dir / "secrets.env").write_text(
                "TELEGRAM_BOT_TOKEN=12345:test-token\n",
                encoding="utf-8",
            )

            test_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nagient",
                    "transport",
                    "test",
                    "telegram",
                    "--format",
                    "json",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            test_payload = json.loads(test_process.stdout)

            self.assertEqual(test_payload["status"], "ready")
            self.assertEqual(len(test_payload["transports"]), 1)
            self.assertEqual(test_payload["issues"], [])

    def test_serve_once_stays_alive_enough_to_write_blocked_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            env = {
                **os.environ,
                "PYTHONPATH": str(SRC_ROOT),
                "NAGIENT_HOME": str(home_dir),
            }
            subprocess.run(
                [sys.executable, "-m", "nagient", "init", "--format", "json"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            config_file = home_dir / "config.toml"
            config_file.write_text(
                config_file.read_text(encoding="utf-8").replace(
                    'default_provider = ""\nrequire_provider = false',
                    'default_provider = "openai-codex"\nrequire_provider = true',
                ),
                encoding="utf-8",
            )

            blocked_serve = subprocess.run(
                [sys.executable, "-m", "nagient", "serve", "--once"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(blocked_serve.returncode, 0)

            heartbeat = json.loads(
                (home_dir / "state" / "heartbeat.json").read_text(encoding="utf-8")
            )
            self.assertEqual(heartbeat["runtime_status"], "blocked")

    def test_entrypoint_continues_to_serve_when_reconcile_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            exec_log = root / "nagient-exec.log"

            fake_python = bin_dir / "python"
            fake_python.write_text(
                "\n".join(
                    [
                        "#!/bin/sh",
                        'if [ "${1:-}" = "-m" ] && [ "${2:-}" = "nagient" ]'
                        ' && [ "${3:-}" = "reconcile" ]; then',
                        "  exit 1",
                        "fi",
                        "exit 0",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            fake_python.chmod(0o755)

            fake_nagient = bin_dir / "nagient"
            fake_nagient.write_text(
                "\n".join(
                    [
                        "#!/bin/sh",
                        'printf "%s\\n" "$@" > "${EXEC_LOG}"',
                        "exit 0",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            fake_nagient.chmod(0o755)

            env = {
                **os.environ,
                "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
                "EXEC_LOG": str(exec_log),
                "NAGIENT_CONFIG": str(root / "config.toml"),
                "NAGIENT_SECRETS_FILE": str(root / "secrets.env"),
                "NAGIENT_TOOL_SECRETS_FILE": str(root / "tool-secrets.env"),
                "NAGIENT_PLUGINS_DIR": str(root / "plugins"),
                "NAGIENT_TOOLS_DIR": str(root / "tools"),
                "NAGIENT_PROVIDERS_DIR": str(root / "providers"),
                "NAGIENT_CREDENTIALS_DIR": str(root / "credentials"),
                "NAGIENT_STATE_DIR": str(root / "state"),
                "NAGIENT_LOG_DIR": str(root / "logs"),
                "NAGIENT_RELEASES_DIR": str(root / "releases"),
            }

            process = subprocess.run(
                ["sh", "docker/scripts/entrypoint.sh", "nagient", "serve"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            self.assertEqual(process.returncode, 0)
            self.assertEqual(exec_log.read_text(encoding="utf-8").strip(), "serve")
            self.assertIn("continuing to serve for recovery", process.stderr)

    def test_status_text_is_compact_and_host_oriented(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            env = {
                **os.environ,
                "PYTHONPATH": str(SRC_ROOT),
                "NAGIENT_HOME": str(home_dir),
                "NAGIENT_HOST_HOME": str(home_dir),
            }
            subprocess.run(
                [sys.executable, "-m", "nagient", "init", "--format", "json"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            subprocess.run(
                [sys.executable, "-m", "nagient", "reconcile", "--format", "json"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            status_process = subprocess.run(
                [sys.executable, "-m", "nagient", "status"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            self.assertIn("Nagient Status", status_process.stdout)
            self.assertIn("Overview", status_process.stdout)
            self.assertIn(f"@config: {home_dir / 'config.toml'}", status_process.stdout)
            self.assertIn("Next Steps", status_process.stdout)
            self.assertNotIn("effective_config.settings.version", status_process.stdout)
            self.assertNotIn("activation.effective_config", status_process.stdout)
            self.assertNotIn("Already up to date", status_process.stdout)

    def test_paths_command_and_interactive_setup_workspace_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            env = {
                **os.environ,
                "PYTHONPATH": str(SRC_ROOT),
                "NAGIENT_HOME": str(home_dir),
            }
            subprocess.run(
                [sys.executable, "-m", "nagient", "init", "--format", "json"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            paths_process = subprocess.run(
                [sys.executable, "-m", "nagient", "paths"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("Nagient Paths", paths_process.stdout)
            self.assertIn("@config", paths_process.stdout)

            setup_process = subprocess.run(
                [sys.executable, "-m", "nagient", "setup"],
                cwd=PROJECT_ROOT,
                env=env,
                input="4\n1\n@home/project\n0\n0\n",
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("Nagient Setup", setup_process.stdout)
            config_text = (home_dir / "config.toml").read_text(encoding="utf-8")
            self.assertIn(f'root = "{(home_dir / "project").resolve()}"', config_text)

    def test_auth_login_status_and_provider_models_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            env = {
                **os.environ,
                "PYTHONPATH": str(SRC_ROOT),
                "NAGIENT_HOME": str(home_dir),
            }
            subprocess.run(
                [sys.executable, "-m", "nagient", "init", "--format", "json"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            config_file = home_dir / "config.toml"
            config_text = config_file.read_text(encoding="utf-8").replace(
                'default_provider = ""',
                'default_provider = "demo"',
            )
            config_file.write_text(
                config_text
                + "\n".join(
                    [
                        "[providers.demo]",
                        'plugin = "custom.provider"',
                        "enabled = true",
                        'auth = "stored_token"',
                        'base_url = "https://example.invalid"',
                        'model = "custom-model"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nagient",
                    "provider",
                    "scaffold",
                    "--plugin-id",
                    "custom.provider",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            login_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nagient",
                    "auth",
                    "login",
                    "demo",
                    "--token",
                    "demo-token",
                    "--format",
                    "json",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            login_payload = json.loads(login_process.stdout)
            self.assertTrue(login_payload["provider"]["authenticated"])

            status_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nagient",
                    "auth",
                    "status",
                    "demo",
                    "--format",
                    "json",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            status_payload = json.loads(status_process.stdout)
            self.assertTrue(status_payload["provider"]["authenticated"])

            models_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nagient",
                    "provider",
                    "models",
                    "demo",
                    "--format",
                    "json",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            models_payload = json.loads(models_process.stdout)
            self.assertEqual(models_payload["models"][0]["model_id"], "custom-model")

    def test_setup_commands_write_runtime_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            env = {
                **os.environ,
                "PYTHONPATH": str(SRC_ROOT),
                "NAGIENT_HOME": str(home_dir),
            }
            subprocess.run(
                [sys.executable, "-m", "nagient", "init", "--format", "json"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            provider_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nagient",
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
                    "base_url=https://api.openai.com/v1",
                    "--format",
                    "json",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            provider_payload = json.loads(provider_process.stdout)
            self.assertEqual(provider_payload["provider_id"], "openai")
            self.assertTrue(provider_payload["enabled"])
            self.assertTrue(provider_payload["default"])

            transport_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nagient",
                    "setup",
                    "transport",
                    "webhook",
                    "--enable",
                    "--set",
                    "listen_port=9090",
                    "--set",
                    "path=/hook",
                    "--format",
                    "json",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            transport_payload = json.loads(transport_process.stdout)
            self.assertEqual(transport_payload["transport_id"], "webhook")
            self.assertTrue(transport_payload["enabled"])

            workspace_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nagient",
                    "setup",
                    "workspace",
                    "--root",
                    "/tmp/project",
                    "--mode",
                    "unsafe",
                    "--format",
                    "json",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            workspace_payload = json.loads(workspace_process.stdout)
            self.assertEqual(workspace_payload["workspace"]["root"], "/tmp/project")
            self.assertEqual(workspace_payload["workspace"]["mode"], "unsafe")

            agent_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nagient",
                    "setup",
                    "agent",
                    "--system-prompt-file",
                    "@prompts/custom-system.md",
                    "--max-turns",
                    "6",
                    "--hard-message-limit",
                    "120",
                    "--no-dynamic-focus",
                    "--dynamic-focus-messages",
                    "15",
                    "--summary-trigger-messages",
                    "18",
                    "--retrieval-max-results",
                    "9",
                    "--log-level",
                    "debug",
                    "--json-logs",
                    "--no-log-events",
                    "--format",
                    "json",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            agent_payload = json.loads(agent_process.stdout)
            self.assertEqual(agent_payload["agent"]["max_turns"], 6)

            config_text = (home_dir / "config.toml").read_text(encoding="utf-8")
            self.assertIn('default_provider = "openai"', config_text)
            self.assertIn("require_provider = true", config_text)
            self.assertIn("[providers.openai]", config_text)
            self.assertIn('model = "gpt-4.1-mini"', config_text)
            self.assertIn('base_url = "https://api.openai.com/v1"', config_text)
            self.assertIn("[transports.webhook]", config_text)
            self.assertIn("listen_port = 9090", config_text)
            self.assertIn('path = "/hook"', config_text)
            self.assertIn("[workspace]", config_text)
            self.assertIn('root = "/tmp/project"', config_text)
            self.assertIn('system_prompt_file = "', config_text)
            self.assertIn("max_turns = 6", config_text)
            self.assertIn("[agent.memory]", config_text)
            self.assertIn("hard_message_limit = 120", config_text)
            self.assertIn("dynamic_focus_enabled = false", config_text)
            self.assertIn("[agent.logging]", config_text)
            self.assertIn('level = "debug"', config_text)

    def test_setup_provider_auto_selects_first_enabled_profile_as_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            env = {
                **os.environ,
                "PYTHONPATH": str(SRC_ROOT),
                "NAGIENT_HOME": str(home_dir),
            }
            subprocess.run(
                [sys.executable, "-m", "nagient", "init", "--format", "json"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            provider_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nagient",
                    "setup",
                    "provider",
                    "openai",
                    "--enable",
                    "--auth",
                    "api_key",
                    "--secret-name",
                    "OPENAI_API_KEY",
                    "--format",
                    "json",
                ],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            provider_payload = json.loads(provider_process.stdout)

            self.assertTrue(provider_payload["default"])
            config_text = (home_dir / "config.toml").read_text(encoding="utf-8")
            self.assertIn('default_provider = "openai"', config_text)


if __name__ == "__main__":
    unittest.main()
