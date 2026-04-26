from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import TracebackType
from typing import Any, cast
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

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        del exc_type, exc, tb
        return None


def _response(payload: dict[str, Any]) -> _FakeResponse:
    return _FakeResponse(payload)


class ProviderBuiltinsTests(unittest.TestCase):
    def test_openai_builtin_parses_model_listing(self) -> None:
        plugin = cast(
            Any,
            next(
            provider.implementation
            for provider in builtin_providers()
            if provider.manifest.plugin_id == "builtin.openai"
            ),
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
        plugin = cast(
            Any,
            next(
            provider.implementation
            for provider in builtin_providers()
            if provider.manifest.plugin_id == "builtin.gemini"
            ),
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
        plugin = cast(
            Any,
            next(
            provider.implementation
            for provider in builtin_providers()
            if provider.manifest.plugin_id == "builtin.openai_codex"
            ),
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
        plugin = cast(
            Any,
            next(
            provider.implementation
            for provider in builtin_providers()
            if provider.manifest.plugin_id == "builtin.openai_codex"
            ),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            auth_file = Path(temp_dir) / "auth.json"
            auth_file.write_text(json.dumps({"OPENAI_API_KEY": "sk-codex"}), encoding="utf-8")
            with patch.dict(
                os.environ,
                {"NAGIENT_OPENAI_CODEX_AUTH_FILE": str(auth_file)},
                clear=False,
            ):
                status = plugin.auth_status(
                    "openai-codex",
                    {"auth": "codex_auth_file"},
                    {},
                    None,
                )

        self.assertTrue(status.authenticated)
        self.assertEqual(status.status, "ready")

    def test_openai_codex_begin_login_returns_oauth_authorization_url(self) -> None:
        plugin = cast(
            Any,
            next(
            provider.implementation
            for provider in builtin_providers()
            if provider.manifest.plugin_id == "builtin.openai_codex"
            ),
        )

        session = plugin.begin_login(
            "openai-codex",
            {"auth": "oauth_browser"},
            {},
            None,
        )

        self.assertEqual(session.auth_mode, "oauth_browser")
        self.assertEqual(session.submission_mode, "callback_url")
        self.assertIn("auth.openai.com/oauth/authorize", session.authorization_url or "")
        self.assertEqual(
            session.callback_url,
            "http://127.0.0.1:1455/auth/callback",
        )

    def test_openai_codex_complete_login_exchanges_callback_url_for_tokens(self) -> None:
        plugin = cast(
            Any,
            next(
            provider.implementation
            for provider in builtin_providers()
            if provider.manifest.plugin_id == "builtin.openai_codex"
            ),
        )

        def opener(request: Any, timeout: int = 15) -> _FakeResponse:
            del timeout
            self.assertEqual(request.method, "POST")
            self.assertIn("https://auth.openai.com/oauth/token", request.full_url)
            return _response(
                {
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "expires_in": 3600,
                    "scope": "openid offline_access model.request",
                }
            )

        plugin = replace(plugin, http_client=JsonHttpClient(opener=cast(Any, opener)))
        session = plugin.begin_login("openai-codex", {"auth": "oauth_browser"}, {}, None)
        state = session.metadata["state"]

        record = plugin.complete_login(
            "openai-codex",
            {"auth": "oauth_browser"},
            None,
            session,
            callback_url=f"http://127.0.0.1:1455/auth/callback?code=demo-code&state={state}",
        )

        self.assertEqual(record.auth_mode, "oauth_browser")
        self.assertEqual(record.data["access_token"], "access-token")
        self.assertEqual(record.data["refresh_token"], "refresh-token")


if __name__ == "__main__":
    unittest.main()
