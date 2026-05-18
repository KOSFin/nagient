from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from nagient.app.configuration import WorkspaceConfig
from nagient.app.settings import Settings
from nagient.domain.entities.workspace import WorkspaceMetadata
from nagient.workspace.manager import WorkspaceLayout
from nagient.tools.registry import ToolPluginRegistry
from nagient.tools.scaffold import scaffold_tool_plugin
from nagient.tools.base import ToolExecutionContext


class ToolPluginRegistryTests(unittest.TestCase):
    def test_registry_discovers_builtins_and_custom_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tools_dir = Path(temp_dir) / "tools"
            scaffold_tool_plugin(
                plugin_id="custom.tool",
                output_dir=tools_dir / "custom.tool",
            )

            discovery = ToolPluginRegistry().discover(tools_dir)

            self.assertIn("workspace.fs", discovery.plugins)
            self.assertIn("system.backup", discovery.plugins)
            self.assertIn("custom.tool", discovery.plugins)
            self.assertTrue(discovery.plugins["custom.tool"].manifest.config_fields)
            self.assertEqual(discovery.issues, [])

    def test_registry_discovers_process_runtime_tool(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tools_dir = root / "tools"
            plugin_dir = tools_dir / "custom.process"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "tool.toml").write_text(
                "\n".join(
                    [
                        'id = "custom.process"',
                        'type = "tool"',
                        'version = "0.1.0"',
                        'display_name = "Custom Process"',
                        'namespace = "custom.process"',
                        'runtime = "process"',
                        'entrypoint = "tool.py"',
                        'capabilities = ["custom"]',
                        "",
                        "[[functions]]",
                        'name = "custom.process.echo"',
                        'binding = "echo"',
                        'description = "Echo through process runtime."',
                        'permissions = ["custom.echo"]',
                        "input_schema = { type = \"object\" }",
                        "output_schema = { type = \"object\" }",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            (plugin_dir / "tool.py").write_text(
                "\n".join(
                    [
                        "import json, sys",
                        "payload = json.loads(sys.stdin.read())",
                        "if payload.get('method') == 'selftest':",
                        "    print(json.dumps({'status': 'success', 'issues': []}))",
                        "elif payload.get('method') == 'execute':",
                        "    print(json.dumps({'status': 'success', 'output': {'echo': payload['arguments']}}))",
                        "else:",
                        "    print(json.dumps({'status': 'success'}))",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            discovery = ToolPluginRegistry().discover(tools_dir)
            plugin = discovery.plugins["custom.process"]
            settings = Settings.from_env({"NAGIENT_HOME": str(root / ".nagient")})
            layout = WorkspaceLayout(
                settings=settings,
                config=WorkspaceConfig(root=root, mode="bounded"),
                root=root,
                nagient_dir=root / ".nagient-workspace",
                metadata=WorkspaceMetadata(
                    workspace_id="workspace-1",
                    root=str(root),
                    mode="bounded",
                    nagient_dir=str(root / ".nagient-workspace"),
                    created_at="2026-01-01T00:00:00Z",
                    updated_at="2026-01-01T00:00:00Z",
                ),
                memory_dir=root / ".nagient-workspace" / "memory",
                notes_dir=root / ".nagient-workspace" / "notes",
                plans_dir=root / ".nagient-workspace" / "plans",
                jobs_dir=root / ".nagient-workspace" / "jobs",
                scripts_dir=root / ".nagient-workspace" / "scripts",
                state_dir=root / ".nagient-state",
                backups_dir=root / ".nagient-backups",
                protected_paths=(),
            )
            context = ToolExecutionContext(
                settings=settings,
                workspace=layout,
                workspace_manager=SimpleNamespace(),
                tool_id="custom_process",
                plugin_id="custom.process",
                config={},
                secret_broker=SimpleNamespace(),
                backup_manager=SimpleNamespace(),
                request_interaction=lambda request: request,
                request_approval=lambda request: request,
                invoke_reconcile=lambda: {},
                invoke_assistant_resume=lambda response: {},
            )

            self.assertEqual(plugin.runtime, "process")
            self.assertEqual(
                plugin.implementation.execute(
                    "custom.process.echo",
                    {"text": "hello"},
                    context,
                ),
                {"echo": {"text": "hello"}},
            )


if __name__ == "__main__":
    unittest.main()
