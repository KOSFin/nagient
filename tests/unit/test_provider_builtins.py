from __future__ import annotations

import json
import unittest
from dataclasses import replace
from typing import Any

from nagient.providers.builtin import builtin_providers
from nagient.providers.http import JsonHttpClient


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb
        return None


class ProviderBuiltinsTests(unittest.TestCase):
    def test_openai_builtin_parses_model_listing(self) -> None:
        plugin = next(
            provider.implementation
            for provider in builtin_providers()
            if provider.manifest.plugin_id == "builtin.openai"
        )
        plugin = replace(
            plugin,
            http_client=JsonHttpClient(
                opener=lambda request, timeout=15: _FakeResponse(
                    {"data": [{"id": "gpt-4.1-mini"}]}
                )
            ),
        )

        models = plugin.list_models(
            "openai",
            {"auth": "api_key", "api_key_secret": "OPENAI_API_KEY"},
            {"OPENAI_API_KEY": "sk-test"},
            None,
        )

        self.assertEqual(models[0].model_id, "gpt-4.1-mini")

    def test_gemini_builtin_parses_model_listing(self) -> None:
        plugin = next(
            provider.implementation
            for provider in builtin_providers()
            if provider.manifest.plugin_id == "builtin.gemini"
        )
        plugin = replace(
            plugin,
            http_client=JsonHttpClient(
                opener=lambda request, timeout=15: _FakeResponse(
                    {"models": [{"name": "models/gemini-2.5-pro", "displayName": "Gemini 2.5 Pro"}]}
                )
            ),
        )

        models = plugin.list_models(
            "gemini",
            {"auth": "api_key", "api_key_secret": "GEMINI_API_KEY"},
            {"GEMINI_API_KEY": "gm-test"},
            None,
        )

        self.assertEqual(models[0].display_name, "Gemini 2.5 Pro")


if __name__ == "__main__":
    unittest.main()
