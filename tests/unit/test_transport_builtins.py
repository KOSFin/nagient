from __future__ import annotations

import unittest
from typing import Any, cast

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


if __name__ == "__main__":
    unittest.main()
