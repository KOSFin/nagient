from __future__ import annotations

from nagient.plugins.builtin import WebhookTransportPlugin


def build_plugin() -> WebhookTransportPlugin:
    return WebhookTransportPlugin()
