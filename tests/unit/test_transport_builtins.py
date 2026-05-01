from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from nagient.plugins.base import TransportRuntimeContext
from nagient.plugins.builtin import builtin_plugins


class TransportBuiltinsTests(unittest.TestCase):
    def test_telegram_accepts_numeric_default_chat_id(self) -> None:
        plugin = cast(
            Any,
            next(
                transport.implementation
                for transport in builtin_plugins()
                if transport.manifest.plugin_id == "builtin.telegram"
            ),
        )

        issues = plugin.validate_config(
            "telegram",
            {
                "bot_token_secret": "TELEGRAM_BOT_TOKEN",
                "default_chat_id": 1522105862,
            },
            {"TELEGRAM_BOT_TOKEN": "12345:test-token"},
        )

        self.assertFalse(
            any(issue.code == "transport.telegram.invalid_chat_id" for issue in issues)
        )

    def test_telegram_healthcheck_is_clean_when_runtime_support_is_built_in(self) -> None:
        plugin = cast(
            Any,
            next(
                transport.implementation
                for transport in builtin_plugins()
                if transport.manifest.plugin_id == "builtin.telegram"
            ),
        )

        issues = plugin.healthcheck(
            "telegram",
            {"bot_token_secret": "TELEGRAM_BOT_TOKEN"},
            {"TELEGRAM_BOT_TOKEN": "12345:test-token"},
        )

        self.assertEqual(issues, [])

    def test_telegram_normalizes_message_event_with_reply_target(self) -> None:
        plugin = cast(
            Any,
            next(
                transport.implementation
                for transport in builtin_plugins()
                if transport.manifest.plugin_id == "builtin.telegram"
            ),
        )

        normalized = plugin.normalize_inbound_event(
            {
                "update_id": 42,
                "message": {
                    "message_id": 7,
                    "text": "hello",
                    "chat": {"id": 1522105862},
                    "from": {"id": 100, "first_name": "D"},
                },
            }
        )

        self.assertEqual(normalized["event_type"], "message")
        self.assertEqual(normalized["text"], "hello")
        self.assertEqual(normalized["reply_target"], {"chat_id": "1522105862"})

    def test_telegram_poll_inbound_events_persists_last_update_id(self) -> None:
        plugin = cast(
            Any,
            next(
                transport.implementation
                for transport in builtin_plugins()
                if transport.manifest.plugin_id == "builtin.telegram"
            ),
        )

        class _TelegramHttpClient:
            def post_json(
                self,
                url: str,
                payload: dict[str, object],
                *,
                headers: dict[str, str] | None = None,
                query: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> dict[str, object]:
                del headers, query, timeout
                self.seen_url = url
                self.seen_payload = dict(payload)
                return {
                    "ok": True,
                    "result": [
                        {
                            "update_id": 9,
                            "message": {
                                "message_id": 1,
                                "text": "hi",
                                "chat": {"id": 123},
                            },
                        }
                    ],
                }

        plugin.http_client = _TelegramHttpClient()

        with tempfile.TemporaryDirectory() as temp_dir:
            plugin.bind_runtime(
                "telegram",
                TransportRuntimeContext(
                    state_dir=Path(temp_dir),
                    log=lambda message: None,
                ),
            )
            plugin.start(
                "telegram",
                {"bot_token_secret": "TELEGRAM_BOT_TOKEN"},
                {"TELEGRAM_BOT_TOKEN": "12345:test-token"},
            )

            updates = plugin.poll_inbound_events(
                "telegram",
                {"bot_token_secret": "TELEGRAM_BOT_TOKEN"},
                {"TELEGRAM_BOT_TOKEN": "12345:test-token"},
            )

            self.assertEqual(len(updates), 1)
            state_path = Path(temp_dir) / "telegram-state.json"
            state_payload = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state_payload["last_update_id"], 9)

    def test_telegram_send_message_uses_payload_contract(self) -> None:
        plugin = cast(
            Any,
            next(
                transport.implementation
                for transport in builtin_plugins()
                if transport.manifest.plugin_id == "builtin.telegram"
            ),
        )

        class _TelegramHttpClient:
            def post_json(
                self,
                url: str,
                payload: dict[str, object],
                *,
                headers: dict[str, str] | None = None,
                query: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> dict[str, object]:
                del headers, query, timeout
                self.seen_url = url
                self.seen_payload = dict(payload)
                return {
                    "ok": True,
                    "result": {
                        "message_id": 5,
                        "chat": {"id": payload["chat_id"]},
                    },
                }

        plugin.http_client = _TelegramHttpClient()

        result = plugin.send_message(
            {
                "chat_id": "1522105862",
                "text": "hello",
                "_token": "12345:test-token",
                "_transport_config": {},
            }
        )

        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["chat_id"], "1522105862")

    def test_telegram_send_typing_and_edit_delete_reaction_use_runtime_payload(self) -> None:
        plugin = cast(
            Any,
            next(
                transport.implementation
                for transport in builtin_plugins()
                if transport.manifest.plugin_id == "builtin.telegram"
            ),
        )

        class _TelegramHttpClient:
            def __init__(self) -> None:
                self.seen_methods: list[tuple[str, dict[str, object]]] = []

            def post_json(
                self,
                url: str,
                payload: dict[str, object],
                *,
                headers: dict[str, str] | None = None,
                query: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> dict[str, object]:
                del headers, query, timeout
                self.seen_methods.append((url.rsplit("/", 1)[-1], dict(payload)))
                if url.endswith("/editMessageText"):
                    return {"ok": True, "result": True}
                if url.endswith("/deleteMessage"):
                    return {"ok": True, "result": True}
                if url.endswith("/setMessageReaction"):
                    return {"ok": True, "result": True}
                return {"ok": True, "result": True}

        http_client = _TelegramHttpClient()
        plugin.http_client = http_client
        payload = {
            "chat_id": "1522105862",
            "message_id": "77",
            "text": "updated",
            "emoji": "🔥",
            "_token": "12345:test-token",
            "_transport_config": {},
        }

        self.assertEqual(plugin.send_typing(payload)["status"], "sent")
        self.assertEqual(plugin.edit_message(payload)["status"], "edited")
        self.assertEqual(plugin.delete_message(payload)["status"], "deleted")
        self.assertEqual(plugin.set_reaction(payload)["status"], "reacted")
        self.assertEqual(
            [method for method, _ in http_client.seen_methods],
            [
                "sendChatAction",
                "editMessageText",
                "deleteMessage",
                "setMessageReaction",
            ],
        )

    def test_telegram_normalizes_edited_message_event(self) -> None:
        plugin = cast(
            Any,
            next(
                transport.implementation
                for transport in builtin_plugins()
                if transport.manifest.plugin_id == "builtin.telegram"
            ),
        )

        normalized = plugin.normalize_inbound_event(
            {
                "update_id": 42,
                "edited_message": {
                    "message_id": 9,
                    "text": "edited",
                    "chat": {"id": 1522105862},
                    "from": {"id": 100, "first_name": "D"},
                },
            }
        )

        self.assertEqual(normalized["event_type"], "edited_message")
        self.assertEqual(normalized["message_id"], "9")
        self.assertEqual(normalized["reply_target"], {"chat_id": "1522105862"})


if __name__ == "__main__":
    unittest.main()
