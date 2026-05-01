from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from nagient.domain.entities.system_state import CheckIssue
from nagient.plugins.base import (
    BaseTransportPlugin,
    LoadedTransportPlugin,
    TransportPluginManifest,
    TransportRuntimeContext,
)
from nagient.providers.http import JsonHttpClient, ProviderHttpError
from nagient.version import __version__


class ConsoleTransportPlugin(BaseTransportPlugin):
    manifest = TransportPluginManifest(
        plugin_id="builtin.console",
        display_name="Console Transport",
        version=__version__,
        namespace="console",
        entrypoint="builtin",
        required_slots={
            "send_message": "console.sendMessage",
            "send_notification": "console.sendNotification",
            "normalize_inbound_event": "console.normalizeInboundEvent",
            "poll_inbound_events": "console.pollInboundEvents",
            "healthcheck": "console.healthcheck",
            "selftest": "console.selftest",
            "start": "console.start",
            "stop": "console.stop",
        },
        function_bindings={
            "console.sendMessage": "send_message",
            "console.sendNotification": "send_notification",
            "console.normalizeInboundEvent": "normalize_inbound_event",
            "console.pollInboundEvents": "poll_inbound_events",
            "console.healthcheck": "healthcheck",
            "console.selftest": "self_test",
            "console.start": "start",
            "console.stop": "stop",
            "console.renderNotice": "render_notice",
        },
        custom_functions=["console.renderNotice"],
        optional_config=["stream"],
        instruction_template=(
            "Use console.sendMessage for normal replies and console.sendNotification for notices. "
            "The console transport is the universal fallback channel."
        ),
    )

    def validate_config(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        del secrets
        stream = config.get("stream", "stdout")
        if stream not in {"stdout", "stderr"}:
            return [
                CheckIssue(
                    severity="error",
                    code="transport.console.invalid_stream",
                    message=f"Transport {transport_id!r} must use stream stdout or stderr.",
                    source=transport_id,
                )
            ]
        return []

    def send_message(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "queued", "payload": payload}

    def send_notification(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "queued", "payload": payload}

    def normalize_inbound_event(self, payload: object) -> dict[str, object]:
        return {"kind": "console", "event_type": "unknown", "payload": payload}

    def self_test(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        del transport_id, config, secrets
        return []

    def render_notice(self, text: str) -> dict[str, object]:
        return {"status": "rendered", "text": text}


class WebhookTransportPlugin(BaseTransportPlugin):
    manifest = TransportPluginManifest(
        plugin_id="builtin.webhook",
        display_name="Webhook Transport",
        version=__version__,
        namespace="webhook",
        entrypoint="builtin",
        required_slots={
            "send_message": "webhook.sendMessage",
            "send_notification": "webhook.sendNotification",
            "normalize_inbound_event": "webhook.normalizeInboundEvent",
            "poll_inbound_events": "webhook.pollInboundEvents",
            "healthcheck": "webhook.healthcheck",
            "selftest": "webhook.selftest",
            "start": "webhook.start",
            "stop": "webhook.stop",
        },
        function_bindings={
            "webhook.sendMessage": "send_message",
            "webhook.sendNotification": "send_notification",
            "webhook.normalizeInboundEvent": "normalize_inbound_event",
            "webhook.pollInboundEvents": "poll_inbound_events",
            "webhook.healthcheck": "healthcheck",
            "webhook.selftest": "self_test",
            "webhook.start": "start",
            "webhook.stop": "stop",
            "webhook.acceptEvent": "accept_event",
            "webhook.replyJson": "reply_json",
        },
        custom_functions=["webhook.acceptEvent", "webhook.replyJson"],
        required_config=["path"],
        optional_config=["listen_host", "listen_port", "shared_secret_name"],
        secret_config=["shared_secret_name"],
        instruction_template=(
            "Use webhook.sendNotification for system notices and webhook.sendMessage for "
            "machine-readable replies. When a webhook payload arrives, normalize it first."
        ),
    )

    def validate_config(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        issues: list[CheckIssue] = []
        path = config.get("path")
        if not isinstance(path, str) or not path.startswith("/"):
            issues.append(
                CheckIssue(
                    severity="error",
                    code="transport.webhook.invalid_path",
                    message=f"Transport {transport_id!r} must define a path starting with '/'.",
                    source=transport_id,
                )
            )
        port = config.get("listen_port", 8080)
        if not isinstance(port, int) or not 1 <= port <= 65535:
            issues.append(
                CheckIssue(
                    severity="error",
                    code="transport.webhook.invalid_port",
                    message=f"Transport {transport_id!r} must define a valid listen_port.",
                    source=transport_id,
                )
            )
        shared_secret_name = config.get("shared_secret_name")
        if shared_secret_name:
            if not isinstance(shared_secret_name, str):
                issues.append(
                    CheckIssue(
                        severity="error",
                        code="transport.webhook.invalid_secret_ref",
                        message=f"Transport {transport_id!r} must use a string shared_secret_name.",
                        source=transport_id,
                    )
                )
            elif shared_secret_name not in secrets:
                issues.append(
                    CheckIssue(
                        severity="error",
                        code="transport.webhook.missing_secret",
                        message=(
                            f"Transport {transport_id!r} references missing secret "
                            f"{shared_secret_name!r}."
                        ),
                        source=transport_id,
                        hint="Add the secret to secrets.env or disable the webhook transport.",
                    )
                )
        else:
            issues.append(
                CheckIssue(
                    severity="warning",
                    code="transport.webhook.no_shared_secret",
                    message=f"Transport {transport_id!r} is enabled without a shared secret.",
                    source=transport_id,
                    hint="Configure shared_secret_name to protect the webhook endpoint.",
                )
            )
        return issues

    def send_message(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "queued", "payload": payload}

    def send_notification(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "queued", "payload": payload}

    def normalize_inbound_event(self, payload: object) -> dict[str, object]:
        if isinstance(payload, dict):
            reply_target = payload.get("reply_target")
            return {
                "kind": "webhook",
                "event_type": str(payload.get("event_type", "unknown")),
                "session_id": str(payload.get("session_id", "webhook")),
                "text": str(payload.get("text", "")),
                "reply_target": dict(reply_target) if isinstance(reply_target, dict) else {},
                "payload": dict(payload),
            }
        return {"kind": "webhook", "event_type": "unknown", "payload": payload}

    def self_test(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        del transport_id, config, secrets
        return []

    def accept_event(self, payload: dict[str, object]) -> dict[str, object]:
        return {"accepted": True, "payload": payload}

    def reply_json(self, payload: dict[str, object]) -> dict[str, object]:
        return {"content_type": "application/json", "payload": payload}

    def healthcheck(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        del config, secrets
        return [
            CheckIssue(
                severity="warning",
                code="transport.webhook.helper_only_builtin",
                message=(
                    f"Transport {transport_id!r} uses the built-in webhook helper, which "
                    "does not open an HTTP listener on its own yet."
                ),
                source=transport_id,
                hint=(
                    "Use a custom webhook transport or an external bridge if you need live "
                    "inbound webhook delivery."
                ),
            )
        ]


class TelegramTransportPlugin(BaseTransportPlugin):
    def __init__(self) -> None:
        self.http_client = JsonHttpClient()
        self._runtime_contexts: dict[str, TransportRuntimeContext] = {}
        self._last_update_ids: dict[str, int] = {}

    manifest = TransportPluginManifest(
        plugin_id="builtin.telegram",
        display_name="Telegram Transport",
        version=__version__,
        namespace="telegram",
        entrypoint="builtin",
        required_slots={
            "send_message": "telegram.sendMessage",
            "send_notification": "telegram.sendNotification",
            "normalize_inbound_event": "telegram.normalizeInboundEvent",
            "poll_inbound_events": "telegram.pollInboundEvents",
            "healthcheck": "telegram.healthcheck",
            "selftest": "telegram.selftest",
            "start": "telegram.start",
            "stop": "telegram.stop",
        },
        function_bindings={
            "telegram.sendMessage": "send_message",
            "telegram.sendNotification": "send_notification",
            "telegram.normalizeInboundEvent": "normalize_inbound_event",
            "telegram.pollInboundEvents": "poll_inbound_events",
            "telegram.healthcheck": "healthcheck",
            "telegram.selftest": "self_test",
            "telegram.start": "start",
            "telegram.stop": "stop",
            "telegram.answerCallback": "answer_callback",
            "telegram.showPopup": "show_popup",
        },
        custom_functions=["telegram.answerCallback", "telegram.showPopup"],
        required_config=["bot_token_secret"],
        optional_config=["default_chat_id", "poll_timeout_seconds"],
        secret_config=["bot_token_secret"],
        instruction_template=(
            "Use telegram.sendMessage for normal replies, telegram.sendNotification for notices, "
            "and telegram.showPopup for short user-facing confirmations."
        ),
    )

    def validate_config(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        issues: list[CheckIssue] = []
        secret_name = config.get("bot_token_secret")
        if not isinstance(secret_name, str) or not secret_name:
            issues.append(
                CheckIssue(
                    severity="error",
                    code="transport.telegram.missing_secret_ref",
                    message=f"Transport {transport_id!r} must define bot_token_secret.",
                    source=transport_id,
                )
            )
            return issues
        if secret_name not in secrets:
            issues.append(
                CheckIssue(
                    severity="error",
                    code="transport.telegram.secret_not_found",
                    message=f"Transport {transport_id!r} cannot find secret {secret_name!r}.",
                    source=transport_id,
                    hint="Add TELEGRAM_BOT_TOKEN to secrets.env or disable the transport.",
                )
            )
        default_chat_id = config.get("default_chat_id", "")
        if default_chat_id and not isinstance(default_chat_id, (str, int)):
            issues.append(
                CheckIssue(
                    severity="error",
                    code="transport.telegram.invalid_chat_id",
                    message=(
                        f"Transport {transport_id!r} must use a string or integer "
                        "default_chat_id."
                    ),
                    source=transport_id,
                )
            )
        return issues

    def bind_runtime(
        self,
        transport_id: str,
        runtime: TransportRuntimeContext,
    ) -> None:
        self._runtime_contexts[transport_id] = runtime

    def start(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> None:
        self._resolve_token(config, secrets)
        self._load_state(transport_id)

    def stop(self, transport_id: str) -> None:
        self._save_state(transport_id)

    def send_message(self, payload: dict[str, object]) -> dict[str, object]:
        token = self._resolve_token_from_payload(payload)
        config = self._config_from_payload(payload)
        chat_id = self._resolve_chat_id(config, payload)
        text = str(payload.get("text", "")).strip()
        if not text:
            raise ValueError("telegram.sendMessage requires a non-empty text field.")

        request_payload: dict[str, object] = {
            "chat_id": chat_id,
            "text": text,
        }
        for field_name in [
            "parse_mode",
            "disable_notification",
            "reply_markup",
            "reply_to_message_id",
            "disable_web_page_preview",
        ]:
            if field_name in payload:
                request_payload[field_name] = payload[field_name]
        response = self._telegram_request(
            token,
            "sendMessage",
            request_payload,
            timeout=_telegram_timeout_seconds(config),
        )
        result = _require_telegram_result_object(response, "sendMessage")
        chat_payload = result.get("chat")
        resolved_chat_id = (
            str(chat_payload.get("id", chat_id))
            if isinstance(chat_payload, dict)
            else str(chat_id)
        )
        return {
            "status": "sent",
            "chat_id": resolved_chat_id,
            "message_id": str(result.get("message_id", "")),
        }

    def send_notification(self, payload: dict[str, object]) -> dict[str, object]:
        notification_payload = dict(payload)
        notification_payload.setdefault("disable_notification", True)
        return self.send_message(notification_payload)

    def normalize_inbound_event(self, payload: object) -> dict[str, object]:
        if not isinstance(payload, dict):
            return {"kind": "telegram", "event_type": "unknown", "payload": payload}

        message = payload.get("message")
        if isinstance(message, dict):
            chat = message.get("chat")
            sender = message.get("from")
            chat_id = _optional_telegram_id(chat, "id")
            text = _telegram_message_text(message)
            reply_target: dict[str, object] = {"chat_id": chat_id} if chat_id else {}
            normalized: dict[str, object] = {
                "kind": "telegram",
                "event_type": "message",
                "session_id": f"telegram:{chat_id}" if chat_id else "telegram:unknown",
                "text": text,
                "reply_target": reply_target,
                "payload": dict(payload),
            }
            sender_id = _optional_telegram_id(sender, "id")
            if sender_id is not None:
                normalized["sender_id"] = sender_id
            sender_name = _telegram_sender_name(sender)
            if sender_name:
                normalized["sender_name"] = sender_name
            message_id = message.get("message_id")
            if message_id is not None:
                normalized["message_id"] = str(message_id)
            return normalized

        callback_query = payload.get("callback_query")
        if isinstance(callback_query, dict):
            callback_message = callback_query.get("message")
            chat_id = None
            if isinstance(callback_message, dict):
                chat_id = _optional_telegram_id(callback_message.get("chat"), "id")
            normalized = {
                "kind": "telegram",
                "event_type": "callback_query",
                "session_id": f"telegram:{chat_id}" if chat_id else "telegram:callback",
                "text": str(callback_query.get("data", "")),
                "reply_target": {"chat_id": chat_id} if chat_id else {},
                "payload": dict(payload),
            }
            callback_id = callback_query.get("id")
            if callback_id is not None:
                normalized["callback_query_id"] = str(callback_id)
            return normalized

        return {"kind": "telegram", "event_type": "unknown", "payload": dict(payload)}

    def self_test(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        secret_name = config.get("bot_token_secret")
        if not isinstance(secret_name, str) or secret_name not in secrets:
            return []

        token = secrets[secret_name]
        if ":" not in token or not token.split(":", 1)[0].isdigit():
            return [
                CheckIssue(
                    severity="error",
                    code="transport.telegram.invalid_token_format",
                    message=f"Transport {transport_id!r} uses a token with an unexpected format.",
                    source=transport_id,
                    hint="Telegram bot tokens usually look like '<digits>:<token>'.",
                )
            ]
        return []

    def poll_inbound_events(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[object]:
        token = self._resolve_token(config, secrets)
        request_payload: dict[str, object] = {
            "timeout": _telegram_poll_timeout_seconds(config),
            "allowed_updates": ["message", "callback_query"],
        }
        last_update_id = self._last_update_ids.get(transport_id)
        if last_update_id is not None:
            request_payload["offset"] = last_update_id + 1

        response = self._telegram_request(
            token,
            "getUpdates",
            request_payload,
            timeout=_telegram_poll_timeout_seconds(config) + 5,
        )
        result = _require_telegram_result_list(response, "getUpdates")
        typed_updates = [item for item in result if isinstance(item, dict)]
        if typed_updates:
            update_ids = [
                int(update["update_id"])
                for update in typed_updates
                if "update_id" in update and isinstance(update["update_id"], int)
            ]
            if update_ids:
                self._last_update_ids[transport_id] = max(update_ids)
                self._save_state(transport_id)
        updates: list[object] = list(typed_updates)
        return updates

    def healthcheck(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        del transport_id, config, secrets
        return []

    def answer_callback(self, payload: dict[str, object]) -> dict[str, object]:
        token = self._resolve_token_from_payload(payload)
        callback_id = str(
            payload.get("callback_id", payload.get("callback_query_id", ""))
        ).strip()
        if not callback_id:
            raise ValueError("telegram.answerCallback requires callback_id.")
        request_payload: dict[str, object] = {"callback_query_id": callback_id}
        text = str(payload.get("text", "")).strip()
        if text:
            request_payload["text"] = text
        if "show_alert" in payload:
            request_payload["show_alert"] = bool(payload["show_alert"])
        self._telegram_request(
            token,
            "answerCallbackQuery",
            request_payload,
            timeout=_telegram_timeout_seconds(self._config_from_payload(payload)),
        )
        return {"status": "answered", "callback_id": callback_id}

    def show_popup(self, payload: dict[str, object]) -> dict[str, object]:
        popup_payload = dict(payload)
        popup_payload["show_alert"] = True
        return self.answer_callback(popup_payload)

    def _resolve_token(
        self,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> str:
        secret_name = config.get("bot_token_secret")
        if not isinstance(secret_name, str) or not secret_name:
            raise ValueError("Telegram transport requires bot_token_secret.")
        token = secrets.get(secret_name, "").strip()
        if not token:
            raise ValueError(f"Telegram transport cannot resolve secret {secret_name!r}.")
        return token

    def _resolve_token_from_payload(self, payload: dict[str, object]) -> str:
        token = str(payload.get("_token", "")).strip()
        if not token:
            raise ValueError("Telegram transport runtime token is not attached to payload.")
        return token

    def _config_from_payload(self, payload: dict[str, object]) -> Mapping[str, object]:
        config = payload.get("_transport_config")
        if isinstance(config, dict):
            return config
        return {}

    def _resolve_chat_id(
        self,
        config: Mapping[str, object],
        payload: Mapping[str, object],
    ) -> str:
        raw_chat_id = payload.get("chat_id", config.get("default_chat_id", ""))
        chat_id = str(raw_chat_id).strip()
        if not chat_id:
            raise ValueError(
                "telegram.sendMessage requires chat_id or a configured default_chat_id."
            )
        return chat_id

    def _state_path(self, transport_id: str) -> Path | None:
        runtime = self._runtime_contexts.get(transport_id)
        if runtime is None:
            return None
        return runtime.state_dir / "telegram-state.json"

    def _load_state(self, transport_id: str) -> None:
        state_path = self._state_path(transport_id)
        if state_path is None or not state_path.exists():
            return
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            self._log_runtime(transport_id, "Failed to read Telegram offset state; starting fresh.")
            return
        if not isinstance(payload, dict):
            return
        update_id = payload.get("last_update_id")
        if isinstance(update_id, int):
            self._last_update_ids[transport_id] = update_id

    def _save_state(self, transport_id: str) -> None:
        state_path = self._state_path(transport_id)
        if state_path is None:
            return
        state_path.parent.mkdir(parents=True, exist_ok=True)
        update_id = self._last_update_ids.get(transport_id)
        payload: dict[str, object] = {}
        if update_id is not None:
            payload["last_update_id"] = update_id
        state_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _log_runtime(self, transport_id: str, message: str) -> None:
        runtime = self._runtime_contexts.get(transport_id)
        if runtime is not None:
            runtime.log(message)

    def _telegram_request(
        self,
        token: str,
        method: str,
        payload: dict[str, object],
        *,
        timeout: int,
    ) -> object:
        try:
            return self.http_client.post_json(
                f"https://api.telegram.org/bot{token}/{method}",
                payload,
                timeout=float(timeout),
            )
        except ProviderHttpError as exc:
            raise ValueError(str(exc)) from exc


def builtin_plugins() -> list[LoadedTransportPlugin]:
    plugins: list[BaseTransportPlugin] = [
        ConsoleTransportPlugin(),
        WebhookTransportPlugin(),
        TelegramTransportPlugin(),
    ]
    return [
        LoadedTransportPlugin(
            manifest=plugin.manifest,
            implementation=plugin,
            source="builtin",
        )
        for plugin in plugins
    ]


def _require_telegram_result_object(payload: object, method: str) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError(f"Telegram method {method} returned an invalid response payload.")
    if not bool(payload.get("ok", False)):
        description = str(payload.get("description", "unknown Telegram error"))
        raise ValueError(f"Telegram method {method} failed: {description}")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError(f"Telegram method {method} returned an invalid result object.")
    return dict(result)


def _require_telegram_result_list(payload: object, method: str) -> list[object]:
    if not isinstance(payload, dict):
        raise ValueError(f"Telegram method {method} returned an invalid response payload.")
    if not bool(payload.get("ok", False)):
        description = str(payload.get("description", "unknown Telegram error"))
        raise ValueError(f"Telegram method {method} failed: {description}")
    result = payload.get("result")
    if not isinstance(result, list):
        raise ValueError(f"Telegram method {method} returned an invalid result list.")
    return list(result)


def _telegram_message_text(message: Mapping[str, object]) -> str:
    if isinstance(message.get("text"), str):
        return str(message["text"])
    if isinstance(message.get("caption"), str):
        return str(message["caption"])
    return ""


def _optional_telegram_id(payload: object, key: str) -> str | None:
    if not isinstance(payload, dict):
        return None
    raw_value = payload.get(key)
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    return value or None


def _telegram_sender_name(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    first_name = str(payload.get("first_name", "")).strip()
    last_name = str(payload.get("last_name", "")).strip()
    username = str(payload.get("username", "")).strip()
    combined = " ".join(part for part in [first_name, last_name] if part).strip()
    if combined:
        return combined
    if username:
        return f"@{username}"
    return None


def _telegram_timeout_seconds(config: Mapping[str, object]) -> int:
    raw_value = config.get("timeout_seconds", 15)
    if isinstance(raw_value, int) and raw_value > 0:
        return raw_value
    return 15


def _telegram_poll_timeout_seconds(config: Mapping[str, object]) -> int:
    raw_value = config.get("poll_timeout_seconds", 20)
    if isinstance(raw_value, int) and raw_value > 0:
        return raw_value
    return 20
