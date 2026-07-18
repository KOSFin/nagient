from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock, patch

from nagient.plugins.base import TransportRuntimeContext
from nagient.plugins.registry import TransportPluginRegistry
from nagient.providers.http import ProviderHttpError


class TransportBuiltinsTests(unittest.TestCase):
    def test_telegram_is_loaded_as_bundled_transport_plugin_manifest(self) -> None:
        transport = _telegram_transport()

        self.assertEqual(transport.manifest.plugin_id, "builtin.telegram")
        self.assertEqual(transport.manifest.entrypoint, "transport.py")
        self.assertEqual(transport.manifest.config_schema_file, "schema.json")
        self.assertIn("bundled_transports", transport.source)
        self.assertIn("telegram.sendTyping", transport.manifest.custom_functions)
        self.assertIn("telegram.editMessage", transport.manifest.custom_functions)
        self.assertIn("telegram.deleteMessage", transport.manifest.custom_functions)
        self.assertIn("telegram.setReaction", transport.manifest.custom_functions)

    def test_telegram_accepts_numeric_default_chat_id(self) -> None:
        plugin = _telegram_plugin()

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
        plugin = _telegram_plugin()

        class _UnexpectedTelegramHttpClient:
            def post_json(
                self,
                url: str,
                payload: dict[str, object],
                *,
                headers: dict[str, str] | None = None,
                query: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> dict[str, object]:
                del url, payload, headers, query, timeout
                raise AssertionError("Telegram healthcheck should not perform outbound HTTP.")

        plugin.http_client = _UnexpectedTelegramHttpClient()

        issues = plugin.healthcheck(
            "telegram",
            {"bot_token_secret": "TELEGRAM_BOT_TOKEN"},
            {"TELEGRAM_BOT_TOKEN": "12345:test-token"},
        )

        self.assertEqual(issues, [])

    def test_telegram_validate_config_accepts_proxy_settings(self) -> None:
        plugin = _telegram_plugin()

        issues = plugin.validate_config(
            "telegram",
            {
                "bot_token_secret": "TELEGRAM_BOT_TOKEN",
                "proxy_url": "http://127.0.0.1:8080",
                "proxy_username": "proxy-user",
                "proxy_password_secret": "TELEGRAM_PROXY_PASSWORD",
            },
            {
                "TELEGRAM_BOT_TOKEN": "12345:test-token",
                "TELEGRAM_PROXY_PASSWORD": "secret",
            },
        )

        self.assertEqual(issues, [])

    def test_telegram_builds_proxy_http_client_for_runtime_requests(self) -> None:
        plugin = _telegram_plugin()
        plugin.start(
            "telegram",
            {"bot_token_secret": "TELEGRAM_BOT_TOKEN"},
            {
                "TELEGRAM_BOT_TOKEN": "12345:test-token",
                "TELEGRAM_PROXY_PASSWORD": "secret",
            },
        )
        proxy_client = Mock()
        with patch(
            f"{plugin.__class__.__module__}.build_proxy_json_http_client",
            return_value=proxy_client,
        ) as build_proxy:
            selected = plugin._telegram_http_client(
                {
                    "proxy_url": "https://proxy.example:8443",
                    "proxy_username": "proxy-user",
                    "proxy_password_secret": "TELEGRAM_PROXY_PASSWORD",
                }
            )

        self.assertIs(selected, proxy_client)
        build_proxy.assert_called_once_with(
            "https://proxy.example:8443",
            username="proxy-user",
            password="secret",
            default_timeout=60.0,
        )

    def test_telegram_normalizes_message_event_with_reply_target(self) -> None:
        plugin = _telegram_plugin()

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
        plugin = _telegram_plugin()

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
        plugin = _telegram_plugin()

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
        self.assertEqual(result["chunks"], 1)

    def test_telegram_send_message_uses_generic_scoped_transport_secrets(self) -> None:
        plugin = _telegram_plugin()

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
                del payload, headers, query, timeout
                self.seen_url = url
                return {"ok": True, "result": {"message_id": 5, "chat": {"id": "42"}}}

        http_client = _TelegramHttpClient()
        plugin.http_client = http_client

        result = plugin.send_message(
            {
                "chat_id": "42",
                "text": "hello",
                "_transport_config": {"bot_token_secret": "TELEGRAM_BOT_TOKEN"},
                "_transport_secrets": {"TELEGRAM_BOT_TOKEN": "12345:test-token"},
            }
        )

        self.assertEqual(result["status"], "sent")
        self.assertIn("12345:test-token", http_client.seen_url)

    def test_telegram_send_message_splits_long_text(self) -> None:
        plugin = _telegram_plugin()

        class _TelegramHttpClient:
            def __init__(self) -> None:
                self.seen_payloads: list[dict[str, object]] = []

            def post_json(
                self,
                url: str,
                payload: dict[str, object],
                *,
                headers: dict[str, str] | None = None,
                query: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> dict[str, object]:
                del url, headers, query, timeout
                self.seen_payloads.append(dict(payload))
                return {
                    "ok": True,
                    "result": {
                        "message_id": len(self.seen_payloads),
                        "chat": {"id": payload["chat_id"]},
                    },
                }

        http_client = _TelegramHttpClient()
        plugin.http_client = http_client
        result = plugin.send_message(
            {
                "chat_id": "1522105862",
                "text": "A" * 8500,
                "reply_markup": {"inline_keyboard": []},
                "_token": "12345:test-token",
                "_transport_config": {},
            }
        )

        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["chunks"], 3)
        self.assertEqual(result["message_ids"], ["1", "2", "3"])
        self.assertLessEqual(
            max(len(str(payload["text"])) for payload in http_client.seen_payloads),
            3900,
        )
        self.assertNotIn("reply_markup", http_client.seen_payloads[0])
        self.assertIn("reply_markup", http_client.seen_payloads[-1])

    def test_telegram_send_message_keeps_parse_mode_across_chunks(self) -> None:
        plugin = _telegram_plugin()

        class _TelegramHttpClient:
            def __init__(self) -> None:
                self.seen_payloads: list[dict[str, object]] = []

            def post_json(
                self,
                url: str,
                payload: dict[str, object],
                *,
                headers: dict[str, str] | None = None,
                query: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> dict[str, object]:
                del url, headers, query, timeout
                self.seen_payloads.append(dict(payload))
                return {
                    "ok": True,
                    "result": {
                        "message_id": len(self.seen_payloads),
                        "chat": {"id": payload["chat_id"]},
                    },
                }

        http_client = _TelegramHttpClient()
        plugin.http_client = http_client

        result = plugin.send_message(
            {
                "chat_id": "1522105862",
                "text": "A" * 8500,
                "_token": "12345:test-token",
                "_transport_config": {"default_parse_mode": "HTML"},
            }
        )

        self.assertEqual(result["chunks"], 3)
        self.assertTrue(http_client.seen_payloads)
        self.assertTrue(
            all(payload["parse_mode"] == "HTML" for payload in http_client.seen_payloads)
        )

    def test_telegram_standard_commands_do_not_normalize_as_messages(self) -> None:
        plugin = _telegram_plugin()

        normalized = plugin.normalize_inbound_event(
            {
                "update_id": 42,
                "message": {
                    "message_id": 7,
                    "text": "/start",
                    "chat": {"id": 1522105862},
                    "from": {"id": 100, "first_name": "D"},
                },
            }
        )

        self.assertEqual(normalized["event_type"], "command")
        self.assertEqual(normalized["command"], "start")

    def test_telegram_send_message_redacts_token_from_http_errors(self) -> None:
        plugin = _telegram_plugin()

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
                del payload, headers, query, timeout
                raise ProviderHttpError(f"HTTP 400 from {url}: bad")

        plugin.http_client = _TelegramHttpClient()

        with self.assertRaisesRegex(ValueError, "<redacted:telegram_bot_token>") as error:
            plugin.send_message(
                {
                    "chat_id": "1522105862",
                    "text": "hello",
                    "_token": "12345:test-token",
                    "_transport_config": {},
                }
            )

        self.assertNotIn("12345:test-token", str(error.exception))

    def test_telegram_send_typing_and_edit_delete_reaction_use_runtime_payload(self) -> None:
        plugin = _telegram_plugin()

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
        plugin = _telegram_plugin()

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


def _telegram_transport() -> Any:
    discovery = TransportPluginRegistry().discover(Path("/missing-user-plugins"))
    return discovery.plugins["builtin.telegram"]


def _telegram_plugin() -> Any:
    return cast(Any, _telegram_transport().implementation)


if __name__ == "__main__":
    unittest.main()
