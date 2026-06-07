from __future__ import annotations

from nagient.plugins.builtin import TelegramTransportPlugin


def build_plugin() -> TelegramTransportPlugin:
    return TelegramTransportPlugin()
