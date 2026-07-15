from __future__ import annotations

from collections.abc import Mapping

from nagient.domain.entities.system_state import CheckIssue
from nagient.plugins.base import BaseTransportPlugin


class WebhookTransportPlugin(BaseTransportPlugin):
    """Webhook transport for HTTP-based event delivery."""

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


def build_plugin() -> WebhookTransportPlugin:
    return WebhookTransportPlugin()
