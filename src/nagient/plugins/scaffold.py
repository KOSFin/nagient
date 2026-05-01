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


def scaffold_transport_plugin(
    plugin_id: str,
    output_dir: Path,
    force: bool = False,
) -> ScaffoldResult:
    namespace = plugin_id.split(".")[-1].replace("-", "_")
    exposed_prefix = namespace
    output_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "plugin.toml": _render_plugin_manifest(plugin_id, exposed_prefix),
        "instructions.md": _render_instructions(plugin_id, exposed_prefix),
        "schema.json": _render_schema(),
        "transport.py": _render_transport_python(plugin_id),
        "README.md": _render_readme(plugin_id),
        "tests/test_plugin.py": _render_test_file(plugin_id),
    }

    written_files: list[str] = []
    for relative_path, content in files.items():
        file_path = output_dir / relative_path
        if file_path.exists() and not force:
            msg = f"Refusing to overwrite existing file {file_path} without force=True."
            raise FileExistsError(msg)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        written_files.append(relative_path)

    return ScaffoldResult(
        plugin_id=plugin_id,
        output_dir=output_dir,
        files=written_files,
    )


def _render_plugin_manifest(plugin_id: str, namespace: str) -> str:
    return "\n".join(
        [
            f'id = "{plugin_id}"',
            'type = "transport"',
            'version = "0.1.0"',
            f'display_name = "{plugin_id}"',
            f'namespace = "{namespace}"',
            'entrypoint = "transport.py"',
            'instructions_file = "instructions.md"',
            'config_schema_file = "schema.json"',
            "",
            "required_config = []",
            'optional_config = ["api_key_secret", "poll_timeout_seconds", "timeout_seconds"]',
            'secret_config = ["api_key_secret"]',
            f'custom_functions = ["{namespace}.showPopup"]',
            "",
            "[[config_fields]]",
            'key = "api_key_secret"',
            'label = "API key secret"',
            'help_text = "Optional secret name for an upstream SDK or bridge token."',
            'value_type = "secret"',
            'category = "connection"',
            "secret = true",
            "",
            "[[config_fields]]",
            'key = "poll_timeout_seconds"',
            'label = "Poll timeout"',
            'help_text = "How long the plugin should wait while polling the remote transport."',
            'value_type = "integer"',
            'category = "advanced"',
            "",
            "[[config_fields]]",
            'key = "timeout_seconds"',
            'label = "Request timeout"',
            'help_text = "Network timeout budget for outbound transport API calls."',
            'value_type = "integer"',
            'category = "advanced"',
            "",
            "[required_slots]",
            f'send_message = "{namespace}.sendMessage"',
            f'send_notification = "{namespace}.sendNotification"',
            f'normalize_inbound_event = "{namespace}.normalizeInboundEvent"',
            f'poll_inbound_events = "{namespace}.pollInboundEvents"',
            f'healthcheck = "{namespace}.healthcheck"',
            f'selftest = "{namespace}.selftest"',
            f'start = "{namespace}.start"',
            f'stop = "{namespace}.stop"',
            "",
            "[function_bindings]",
            f'"{namespace}.sendMessage" = "send_message"',
            f'"{namespace}.sendNotification" = "send_notification"',
            f'"{namespace}.normalizeInboundEvent" = "normalize_inbound_event"',
            f'"{namespace}.pollInboundEvents" = "poll_inbound_events"',
            f'"{namespace}.healthcheck" = "healthcheck"',
            f'"{namespace}.selftest" = "self_test"',
            f'"{namespace}.start" = "start"',
            f'"{namespace}.stop" = "stop"',
            f'"{namespace}.showPopup" = "show_popup"',
            "",
        ]
    )


def _render_instructions(plugin_id: str, namespace: str) -> str:
    return "\n".join(
        [
            f"# {plugin_id}",
            "",
            f"Use `{namespace}.sendMessage` for normal replies.",
            f"Use `{namespace}.sendNotification` for notices and system events.",
            (
                f"Use `{namespace}.pollInboundEvents` to return newly available raw transport "
                "events for the runtime loop."
            ),
            (
                f"Use `{namespace}.showPopup` for short contextual confirmations when "
                "the transport supports it."
            ),
            "",
            (
                "This scaffold is intentionally SDK-friendly: you can wrap aiogram, discord.py, "
                "Slack Bolt, or any other Python client inside transport.py."
            ),
            (
                "You do not have to implement a raw webhook bridge unless that matches the "
                "transport you are targeting."
            ),
            "",
            "Always normalize inbound payloads before passing them to the core agent runtime.",
            "",
            "Normalized inbound events should follow this shape whenever possible:",
            "",
            "```json",
            "{",
            '  "kind": "your-transport",',
            '  "event_type": "message",',
            '  "session_id": "stable-session-key",',
            '  "text": "User message text",',
            '  "reply_target": {',
            '    "channel_id": "opaque-reply-target"',
            "  },",
            '  "payload": {}',
            "}",
            "```",
            "",
            "The runtime will merge `reply_target` with `{ \"text\": \"...reply...\" }` and pass",
            f"that payload back into `{namespace}.sendMessage`.",
            "",
        ]
    )


def _render_schema() -> str:
    return "\n".join(
        [
            "{",
            '  "type": "object",',
            '  "properties": {',
            '    "api_key_secret": {',
            '      "type": "string"',
            "    },",
            '    "poll_timeout_seconds": {',
            '      "type": "integer",',
            '      "minimum": 1',
            "    },",
            '    "timeout_seconds": {',
            '      "type": "integer",',
            '      "minimum": 1',
            "    }",
            "  }",
            "}",
            "",
        ]
    )


def _render_transport_python(plugin_id: str) -> str:
    return "\n".join(
        [
            "from __future__ import annotations",
            "",
            "from collections.abc import Mapping",
            "",
            "from nagient.domain.entities.system_state import CheckIssue",
            "from nagient.plugins.base import BaseTransportPlugin",
            "",
            "",
            "class TransportPlugin(BaseTransportPlugin):",
            "    def validate_config(",
            "        self,",
            "        transport_id: str,",
            "        config: Mapping[str, object],",
            "        secrets: Mapping[str, str],",
            "    ) -> list[CheckIssue]:",
            "        issues: list[CheckIssue] = []",
            '        secret_name = config.get("api_key_secret")',
            "        if secret_name:",
            "            if not isinstance(secret_name, str):",
            "                issues.append(",
            "                    CheckIssue(",
            '                        severity="error",',
            '                        code="transport.invalid_secret_ref",',
            "                        message=(",
            '                            f"Transport {transport_id!r} must use a string "',
            '                            "api_key_secret."',
            "                        ),",
            "                        source=transport_id,",
            "                    )",
            "                )",
            "            elif secret_name not in secrets:",
            "                issues.append(",
            "                    CheckIssue(",
            '                        severity="error",',
            '                        code="transport.secret_not_found",',
            "                        message=(",
            '                            f"Transport {transport_id!r} cannot find secret "',
            '                            f"{secret_name!r}."',
            "                        ),",
            "                        source=transport_id,",
            "                    )",
            "                )",
            "        return issues",
            "",
            "    def self_test(",
            "        self,",
            "        transport_id: str,",
            "        config: Mapping[str, object],",
            "        secrets: Mapping[str, str],",
            "    ) -> list[CheckIssue]:",
            "        del transport_id, config, secrets",
            "        return []",
            "",
            "    def poll_inbound_events(",
            "        self,",
            "        transport_id: str,",
            "        config: Mapping[str, object],",
            "        secrets: Mapping[str, str],",
            "    ) -> list[object]:",
            "        del transport_id, config, secrets",
            "        return []",
            "",
            "    def send_message(self, payload: dict[str, object]) -> dict[str, object]:",
            '        return {"status": "queued", "payload": payload}',
            "",
            "    def send_notification(self, payload: dict[str, object]) -> dict[str, object]:",
            '        return {"status": "queued", "payload": payload}',
            "",
            "    def normalize_inbound_event(self, payload: object) -> dict[str, object]:",
            '        return {"kind": "custom", "event_type": "unknown", "payload": payload}',
            "",
            "    def show_popup(self, payload: dict[str, object]) -> dict[str, object]:",
            '        return {"status": "queued", "payload": payload}',
            "",
            "",
            "def build_plugin() -> TransportPlugin:",
            "    return TransportPlugin()",
            "",
        ]
    )


def _render_readme(plugin_id: str) -> str:
    return "\n".join(
        [
            f"# {plugin_id}",
            "",
            "This directory contains a custom Nagient transport plugin scaffold.",
            "",
            (
                "Edit `plugin.toml` to describe the transport contract and "
                "`transport.py` to implement it."
            ),
            (
                "Then configure the plugin in `config.toml` and run "
                "`nagient preflight` or `nagient reconcile`."
            ),
            "",
        ]
    )


def _render_test_file(plugin_id: str) -> str:
    return "\n".join(
        [
            "from __future__ import annotations",
            "",
            "import importlib.util",
            "import sys",
            "import unittest",
            "from pathlib import Path",
            "",
            "",
            "class PluginContractTests(unittest.TestCase):",
            "    def test_build_plugin_returns_object_with_required_methods(self) -> None:",
            "        plugin_path = Path(__file__).resolve().parents[1] / 'transport.py'",
            "        spec = importlib.util.spec_from_file_location('scaffold_plugin', plugin_path)",
            "        self.assertIsNotNone(spec)",
            "        self.assertIsNotNone(spec.loader)",
            "        module = importlib.util.module_from_spec(spec)",
            "        sys.modules['scaffold_plugin'] = module",
            "        assert spec.loader is not None",
            "        spec.loader.exec_module(module)",
            "",
            "        plugin = module.build_plugin()",
            "        for attribute_name in [",
            "            'validate_config',",
            "            'self_test',",
            "            'healthcheck',",
            "            'poll_inbound_events',",
            "            'start',",
            "            'stop',",
            "            'send_message',",
            "            'send_notification',",
            "            'normalize_inbound_event',",
            "            'show_popup',",
            "        ]:",
            "            self.assertTrue(",
            "                callable(getattr(plugin, attribute_name, None)),",
            "                msg=attribute_name,",
            "            )",
            "",
            "",
            "if __name__ == '__main__':",
            "    unittest.main()",
            "",
        ]
    )
