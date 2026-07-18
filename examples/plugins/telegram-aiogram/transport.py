from __future__ import annotations

import asyncio
from collections.abc import Mapping

from nagient.domain.entities.system_state import CheckIssue
from nagient.plugins.base import BaseTransportPlugin


class AiogramTelegramTransport(BaseTransportPlugin):
    def __init__(self) -> None:
        self._offsets: dict[str, int] = {}

    def validate_config(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        issues: list[CheckIssue] = []
        token_name = config.get("bot_token_secret")
        if not isinstance(token_name, str) or token_name not in secrets:
            issues.append(
                CheckIssue(
                    severity="error",
                    code="transport.telegram_aiogram.secret_not_found",
                    message=f"Transport {transport_id!r} cannot find bot token secret.",
                    source=transport_id,
                )
            )
        proxy = config.get("proxy_url")
        if proxy and not isinstance(proxy, str):
            issues.append(
                CheckIssue(
                    severity="error",
                    code="transport.telegram_aiogram.invalid_proxy",
                    message="proxy_url must be a string.",
                    source=transport_id,
                )
            )
        return issues

    def self_test(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        return self.validate_config(transport_id, config, secrets)

    def healthcheck(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        return self.validate_config(transport_id, config, secrets)

    def start(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> None:
        del transport_id, config, secrets

    def stop(self, transport_id: str) -> None:
        self._offsets.pop(transport_id, None)

    def send_message(self, payload: dict[str, object]) -> dict[str, object]:
        config, secrets = _runtime_config(payload)
        chat_id = payload.get("chat_id", config.get("default_chat_id"))
        if chat_id in (None, ""):
            raise ValueError("telegram_aiogram.sendMessage requires chat_id.")
        text = str(payload.get("text", ""))
        result = _run(self._send(config, secrets, chat_id, text, payload))
        return {"status": "sent", "chat_id": str(chat_id), "message_id": result}

    def send_notification(self, payload: dict[str, object]) -> dict[str, object]:
        return self.send_message(payload)

    def normalize_inbound_event(self, payload: object) -> dict[str, object]:
        if not isinstance(payload, dict):
            return {"kind": "telegram", "event_type": "unknown", "payload": payload}
        message = payload.get("message") or payload.get("edited_message")
        if not isinstance(message, dict):
            return {"kind": "telegram", "event_type": "unknown", "payload": payload}
        chat = message.get("chat")
        chat_id = chat.get("id") if isinstance(chat, dict) else None
        return {
            "kind": "telegram",
            "event_type": "message",
            "session_id": f"telegram:{chat_id}",
            "text": str(message.get("text", "")),
            "reply_target": {"chat_id": chat_id},
            "payload": payload,
        }

    def poll_inbound_events(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[object]:
        updates = _run(self._poll(config, secrets, self._offsets.get(transport_id)))
        if updates:
            self._offsets[transport_id] = max(
                int(item["update_id"]) for item in updates if isinstance(item, dict)
            )
        return updates

    async def _send(
        self,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        chat_id: object,
        text: str,
        payload: Mapping[str, object],
    ) -> int:
        async with _bot(config, secrets) as bot:
            message = await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=(
                    str(payload.get("parse_mode", config.get("default_parse_mode", "")))
                    or None
                ),
            )
            return int(message.message_id)

    async def _poll(
        self,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        offset: int | None,
    ) -> list[dict[str, object]]:
        async with _bot(config, secrets) as bot:
            updates = await bot.get_updates(
                offset=offset + 1 if offset is not None else None,
                timeout=int(config.get("poll_timeout_seconds", 30)),
                allowed_updates=["message", "edited_message", "callback_query"],
            )
            return [update.model_dump(mode="json") for update in updates]


def build_plugin() -> BaseTransportPlugin:
    return AiogramTelegramTransport()


def _runtime_config(
    payload: Mapping[str, object],
) -> tuple[Mapping[str, object], Mapping[str, str]]:
    config = payload.get("_transport_config", {})
    secrets = payload.get("_transport_secrets", {})
    return (
        config if isinstance(config, Mapping) else {},
        secrets if isinstance(secrets, Mapping) else {},
    )


def _run(awaitable: object) -> object:
    return asyncio.run(awaitable)  # type: ignore[arg-type]


def _bot(config: Mapping[str, object], secrets: Mapping[str, str]):
    from aiogram import Bot
    from aiogram.client.session.aiohttp import AiohttpSession

    token_name = str(config.get("bot_token_secret", ""))
    token = str(secrets[token_name])
    proxy = str(config.get("proxy_url", "")).strip()
    if proxy:
        username = str(config.get("proxy_username", "")).strip()
        password_name = str(config.get("proxy_password_secret", "")).strip()
        password = str(secrets.get(password_name, ""))
        if username:
            from urllib.parse import quote

            credentials = f"{quote(username)}:{quote(password)}@"
            scheme, rest = proxy.split("://", 1)
            proxy = f"{scheme}://{credentials}{rest}"
        return Bot(token=token, session=AiohttpSession(proxy=proxy))
    return Bot(token=token)
