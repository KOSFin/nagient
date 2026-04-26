from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from nagient.providers.builtin import builtin_providers
from nagient.providers.http import JsonHttpClient


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> _FakeResponse:
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

    def test_openai_codex_builtin_reads_api_key_from_auth_cache(self) -> None:
        plugin = next(
            provider.implementation
            for provider in builtin_providers()
            if provider.manifest.plugin_id == "builtin.openai_codex"
        )
        plugin = replace(
            plugin,
            http_client=JsonHttpClient(
                opener=lambda request, timeout=15: _FakeResponse(
                    {"data": [{"id": "gpt-5-codex"}]}
                )
            ),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            auth_file = Path(temp_dir) / "auth.json"
            auth_file.write_text(json.dumps({"OPENAI_API_KEY": "sk-codex"}), encoding="utf-8")

            models = plugin.list_models(
                "openai-codex",
                {"auth": "codex_auth_file", "auth_file": str(auth_file)},
                {},
                None,
            )

        self.assertEqual(models[0].model_id, "gpt-5-codex")

    def test_openai_codex_auth_status_accepts_env_auth_file_override(self) -> None:
        plugin = next(
            provider.implementation
            for provider in builtin_providers()
            if provider.manifest.plugin_id == "builtin.openai_codex"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            auth_file = Path(temp_dir) / "auth.json"
            auth_file.write_text(json.dumps({"OPENAI_API_KEY": "sk-codex"}), encoding="utf-8")
            with patch.dict(os.environ, {"NAGIENT_OPENAI_CODEX_AUTH_FILE": str(auth_file)}, clear=False):
                status = plugin.auth_status(
                    "openai-codex",
                    {"auth": "codex_auth_file"},
                    {},
                    None,
                )

        self.assertTrue(status.authenticated)
        self.assertEqual(status.status, "ready")


if __name__ == "__main__":
    unittest.main()
