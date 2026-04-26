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
            self.assertIn(f"Config: {home_dir / 'config.toml'}", status_process.stdout)
            self.assertIn("Next Steps", status_process.stdout)
            self.assertNotIn("effective_config.settings.version", status_process.stdout)
            self.assertNotIn("activation.effective_config", status_process.stdout)
            self.assertNotIn("Already up to date", status_process.stdout)

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


if __name__ == "__main__":
    unittest.main()
