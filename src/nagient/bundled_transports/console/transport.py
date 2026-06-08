from __future__ import annotations

from nagient.plugins.builtin import ConsoleTransportPlugin


def build_plugin() -> ConsoleTransportPlugin:
    return ConsoleTransportPlugin()
