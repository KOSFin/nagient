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
from nagient.providers.http import JsonHttpClient, ProviderHttpError


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

    def test_openai_codex_begin_login_supports_device_code(self) -> None:
        plugin = cast(
            Any,
            next(
                provider.implementation
                for provider in builtin_providers()
                if provider.manifest.plugin_id == "builtin.openai_codex"
            ),
        )

        class _DeviceHttpClient:
            def post_json(
                self,
                url: str,
                payload: dict[str, Any],
                *,
                headers: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> dict[str, Any]:
                del headers, timeout
                self.assertEqual(url, "https://auth.openai.com/api/accounts/deviceauth/usercode")
                self.assertEqual(payload["client_id"], "app_EMoamEEZ73f0CkXaXp7hrann")
                return {
                    "device_auth_id": "device-auth-id",
                    "user_code": "ABCD-EFGH",
                    "interval": 7,
                    "expires_in": 1800,
                }

            def __init__(self, case: unittest.TestCase) -> None:
                self.assertEqual = case.assertEqual

        plugin = replace(plugin, http_client=cast(Any, _DeviceHttpClient(self)))

        session = plugin.begin_login("openai-codex", {"auth": "device_code"}, {}, None)

        self.assertEqual(session.auth_mode, "device_code")
        self.assertEqual(session.submission_mode, "device_code")
        self.assertEqual(session.user_code, "ABCD-EFGH")
        self.assertEqual(session.poll_interval_seconds, 7)
        self.assertEqual(session.authorization_url, "https://chatgpt.com/device")

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

    def test_openai_codex_complete_device_code_login_exchanges_tokens(self) -> None:
        plugin = cast(
            Any,
            next(
                provider.implementation
                for provider in builtin_providers()
                if provider.manifest.plugin_id == "builtin.openai_codex"
            ),
        )

        class _DeviceCompletionHttpClient:
            def post_json(
                self,
                url: str,
                payload: dict[str, Any],
                *,
                headers: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> dict[str, Any]:
                del headers, timeout
                if url == "https://auth.openai.com/api/accounts/deviceauth/usercode":
                    self.assertEqual(payload["client_id"], "app_EMoamEEZ73f0CkXaXp7hrann")
                    return {
                        "device_auth_id": "device-auth-id",
                        "user_code": "ABCD-EFGH",
                        "interval": 5,
                        "expires_in": 1800,
                    }
                self.assertEqual(url, "https://auth.openai.com/api/accounts/deviceauth/wait")
                self.assertEqual(payload["device_auth_id"], "device-auth-id")
                self.assertEqual(payload["user_code"], "ABCD-EFGH")
                return {"code": "device-auth-code", "code_verifier": "device-verifier"}

            def post_form_json(
                self,
                url: str,
                form: dict[str, str],
                *,
                headers: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> dict[str, Any]:
                del headers, timeout
                self.assertEqual(url, "https://auth.openai.com/oauth/token")
                self.assertEqual(form["grant_type"], "authorization_code")
                self.assertEqual(form["redirect_uri"], "https://auth.openai.com/deviceauth/callback")
                self.assertEqual(form["code"], "device-auth-code")
                self.assertEqual(form["code_verifier"], "device-verifier")
                return {
                    "access_token": "device-access-token",
                    "refresh_token": "device-refresh-token",
                    "expires_in": 3600,
                }

            def __init__(self, case: unittest.TestCase) -> None:
                self.assertEqual = case.assertEqual

        plugin = replace(plugin, http_client=cast(Any, _DeviceCompletionHttpClient(self)))
        session = plugin.begin_login(
            "openai-codex",
            {"auth": "device_code"},
            {},
            None,
        )
        session = replace(
            session,
            metadata={
                "device_auth_id": "device-auth-id",
                "user_code": "ABCD-EFGH",
            },
        )

        record = plugin.complete_login(
            "openai-codex",
            {"auth": "device_code"},
            None,
            session,
        )

        self.assertEqual(record.auth_mode, "device_code")
        self.assertEqual(record.data["access_token"], "device-access-token")
        self.assertEqual(record.data["refresh_token"], "device-refresh-token")

    def test_openai_codex_chat_falls_back_to_responses_api(self) -> None:
        plugin = cast(
            Any,
            next(
                provider.implementation
                for provider in builtin_providers()
                if provider.manifest.plugin_id == "builtin.openai_codex"
            ),
        )

        class _RetryingClient:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def post_json(
                self,
                url: str,
                payload: dict[str, Any],
                *,
                headers: dict[str, str] | None = None,
                timeout: float | None = None,
            ) -> dict[str, Any]:
                del headers, timeout
                self.calls.append(url)
                if url.endswith("/chat/completions"):
                    raise ProviderHttpError(
                        "HTTP 500 from https://api.openai.com/v1/chat/completions: internal_error"
                    )
                self.assertEqual(url, "https://api.openai.com/v1/responses")
                self.assertEqual(payload["model"], "gpt-5-codex")
                return {"output_text": "hello from responses"}

            def assertEqual(self, left: object, right: object) -> None:
                self_case.assertEqual(left, right)

        self_case = self
        plugin = replace(plugin, http_client=cast(Any, _RetryingClient()))

        response = plugin.generate_message(
            "openai-codex",
            {
                "auth": "api_key",
                "api_key_secret": "CODEX_API_KEY",
                "model": "gpt-5-codex",
            },
            {"CODEX_API_KEY": "sk-codex"},
            None,
            message="hello",
        )

        self.assertEqual(response, "hello from responses")


if __name__ == "__main__":
    unittest.main()
