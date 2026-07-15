"""
Compatibility module for builtin transport plugins.

This module is kept for backward compatibility but no longer contains
transport implementations. All bundled transports (Console, Webhook, Telegram)
now load through the standard manifest-driven plugin discovery system from
src/nagient/bundled_transports/.

This ensures bundled transports work exactly like user-provided plugins,
maintaining architectural consistency.
"""

from __future__ import annotations

from nagient.plugins.base import LoadedTransportPlugin


def builtin_plugins() -> list[LoadedTransportPlugin]:
    """
    Return builtin transport plugins.

    Returns empty list as all bundled transports now load via plugin discovery
    from bundled_transports/ directory using the standard registry mechanism.
    """
    return []
