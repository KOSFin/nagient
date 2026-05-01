from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScaffoldResult:
    plugin_id: str
    output_dir: Path
    files: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "plugin_id": self.plugin_id,
            "output_dir": str(self.output_dir),
            "files": self.files,
        }


def scaffold_tool_plugin(
    plugin_id: str,
    output_dir: Path,
    force: bool = False,
) -> ScaffoldResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "tool.toml": _render_manifest(plugin_id),
        "schema.json": _render_schema(),
        "tool.py": _render_tool_python(plugin_id),
        "README.md": _render_readme(plugin_id),
        "tests/test_tool.py": _render_test_file(plugin_id),
    }

    written_files: list[str] = []
    for relative_path, content in files.items():
        file_path = output_dir / relative_path
        if file_path.exists() and not force:
            raise FileExistsError(
                f"Refusing to overwrite existing file {file_path} without force=True."
            )
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        written_files.append(relative_path)

    return ScaffoldResult(plugin_id=plugin_id, output_dir=output_dir, files=written_files)


def _render_manifest(plugin_id: str) -> str:
    return "\n".join(
        [
            f'id = "{plugin_id}"',
            'type = "tool"',
            'version = "0.1.0"',
            f'display_name = "{plugin_id}"',
            f'namespace = "{plugin_id}"',
            'entrypoint = "tool.py"',
            'config_schema_file = "schema.json"',
            "",
            "required_config = []",
            "optional_config = []",
            'capabilities = ["custom"]',
            "",
            "[[config_fields]]",
            'key = "example_label"',
            'label = "Example label"',
            'help_text = "Demonstrates how custom tool settings appear inside Nagient setup."',
            'value_type = "string"',
            'category = "advanced"',
            "",
            "[[functions]]",
            f'name = "{plugin_id}.echo"',
            'binding = "echo"',
            'description = "Echo the supplied input back to the caller."',
            'permissions = ["custom.echo"]',
            'required_config = []',
            'optional_config = []',
            'secret_bindings = []',
            'required_connectors = []',
            'side_effect = "read"',
            'approval_policy = "never"',
            "dry_run_supported = true",
            "input_schema = { type = \"object\" }",
            "output_schema = { type = \"object\" }",
            "",
        ]
    )


def _render_schema() -> str:
    return "\n".join(
        [
            "{",
            '  "type": "object",',
            '  "properties": {',
            '    "example_label": {',
            '      "type": "string"',
            "    }",
            "  }",
            "}",
            "",
        ]
    )


def _render_tool_python(plugin_id: str) -> str:
    return "\n".join(
        [
            "from __future__ import annotations",
            "",
            "from collections.abc import Mapping",
            "",
            "from nagient.domain.entities.tooling import ToolFunctionManifest, ToolPluginManifest",
            "from nagient.tools.base import BaseToolPlugin, ToolExecutionContext",
            "",
            "",
            "class ToolPlugin(BaseToolPlugin):",
            "    manifest = ToolPluginManifest(",
            f"        plugin_id=\"{plugin_id}\",",
            f"        display_name=\"{plugin_id}\",",
            "        version=\"0.1.0\",",
            f"        namespace=\"{plugin_id}\",",
            "        entrypoint=\"tool.py\",",
            "        functions=[",
            "            ToolFunctionManifest(",
            f"                function_name=\"{plugin_id}.echo\",",
            "                binding=\"echo\",",
            "                description=\"Echo the supplied input back to the caller.\",",
            "                input_schema={\"type\": \"object\"},",
            "                output_schema={\"type\": \"object\"},",
            "                permissions=[\"custom.echo\"],",
            "                dry_run_supported=True,",
            "            )",
            "        ],",
            "    )",
            "",
            "    def echo(",
            "        self,",
            "        arguments: Mapping[str, object],",
            "        context: ToolExecutionContext,",
            "    ) -> dict[str, object]:",
            "        del context",
            "        return {\"echo\": dict(arguments)}",
            "",
            "",
            "def build_plugin() -> BaseToolPlugin:",
            "    return ToolPlugin()",
            "",
        ]
    )


def _render_readme(plugin_id: str) -> str:
    return "\n".join(
        [
            f"# {plugin_id}",
            "",
            "Custom Nagient tool plugin scaffold.",
            "",
        ]
    )


def _render_test_file(plugin_id: str) -> str:
    return "\n".join(
        [
            "from __future__ import annotations",
            "",
            "import unittest",
            "",
            "from tool import build_plugin",
            "",
            "",
            "class ToolPluginTests(unittest.TestCase):",
            "    def test_echo_binding_exists(self) -> None:",
            "        plugin = build_plugin()",
            f"        self.assertEqual(plugin.manifest.plugin_id, \"{plugin_id}\")",
            "",
            "",
            "if __name__ == \"__main__\":",
            "    unittest.main()",
            "",
        ]
    )
