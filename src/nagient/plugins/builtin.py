from __future__ import annotations

from collections.abc import Mapping

from nagient.domain.entities.system_state import CheckIssue
from nagient.plugins.base import BaseTransportPlugin, LoadedTransportPlugin, TransportPluginManifest
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
            "healthcheck": "console.healthcheck",
            "selftest": "console.selftest",
            "start": "console.start",
            "stop": "console.stop",
        },
        function_bindings={
            "console.sendMessage": "send_message",
            "console.sendNotification": "send_notification",
            "console.normalizeInboundEvent": "normalize_inbound_event",
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

    def send_message(self, text: str) -> dict[str, str]:
        return {"status": "queued", "text": text}

    def send_notification(self, text: str) -> dict[str, str]:
        return {"status": "queued", "text": text}

    def normalize_inbound_event(self, payload: object) -> dict[str, object]:
        return {"kind": "console", "payload": payload}

    def self_test(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        del transport_id, config, secrets
        return []

    def render_notice(self, text: str) -> dict[str, str]:
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
            "healthcheck": "webhook.healthcheck",
            "selftest": "webhook.selftest",
            "start": "webhook.start",
            "stop": "webhook.stop",
        },
        function_bindings={
            "webhook.sendMessage": "send_message",
            "webhook.sendNotification": "send_notification",
            "webhook.normalizeInboundEvent": "normalize_inbound_event",
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
        return {"kind": "webhook", "payload": payload}

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


class TelegramTransportPlugin(BaseTransportPlugin):
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
            "healthcheck": "telegram.healthcheck",
            "selftest": "telegram.selftest",
            "start": "telegram.start",
            "stop": "telegram.stop",
        },
        function_bindings={
            "telegram.sendMessage": "send_message",
            "telegram.sendNotification": "send_notification",
            "telegram.normalizeInboundEvent": "normalize_inbound_event",
            "telegram.healthcheck": "healthcheck",
            "telegram.selftest": "self_test",
            "telegram.start": "start",
            "telegram.stop": "stop",
            "telegram.answerCallback": "answer_callback",
            "telegram.showPopup": "show_popup",
        },
        custom_functions=["telegram.answerCallback", "telegram.showPopup"],
        required_config=["bot_token_secret"],
        optional_config=["default_chat_id"],
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
        if default_chat_id and not isinstance(default_chat_id, str):
            issues.append(
                CheckIssue(
                    severity="error",
                    code="transport.telegram.invalid_chat_id",
                    message=f"Transport {transport_id!r} must use a string default_chat_id.",
                    source=transport_id,
                )
            )
        if not default_chat_id:
            issues.append(
                CheckIssue(
                    severity="warning",
                    code="transport.telegram.default_chat_id_not_set",
                    message=(
                        f"Transport {transport_id!r} has no default_chat_id for proactive "
                        "outbound notices."
                    ),
                    source=transport_id,
                    hint=(
                        "This is optional. Set default_chat_id only if Nagient must send "
                        "Telegram messages without an inbound event that already carries chat_id."
                    ),
                )
            )
        return issues

    def send_message(self, chat_id: str, text: str) -> dict[str, str]:
        return {"status": "queued", "chat_id": chat_id, "text": text}

    def send_notification(self, chat_id: str, text: str) -> dict[str, str]:
        return {"status": "queued", "chat_id": chat_id, "text": text}

    def normalize_inbound_event(self, payload: object) -> dict[str, object]:
        return {"kind": "telegram", "payload": payload}

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

    def answer_callback(self, callback_id: str, text: str) -> dict[str, str]:
        return {"status": "queued", "callback_id": callback_id, "text": text}

    def show_popup(self, chat_id: str, text: str) -> dict[str, str]:
        return {"status": "queued", "chat_id": chat_id, "text": text}


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
