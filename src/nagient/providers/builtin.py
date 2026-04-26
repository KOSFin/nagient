from __future__ import annotations

import base64
import calendar
import hashlib
import json
import os
import secrets as secretslib
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from nagient.domain.entities.system_state import (
    AuthSessionState,
    CheckIssue,
    CredentialRecord,
    ProviderAuthStatus,
    ProviderModel,
)
from nagient.providers.base import BaseProviderPlugin, LoadedProviderPlugin, ProviderPluginManifest
from nagient.providers.http import JsonHttpClient, ProviderHttpError

_CODEX_AUTH_FILE_ENV = "NAGIENT_OPENAI_CODEX_AUTH_FILE"
_CODEX_ACCESS_TOKEN_ENV = "NAGIENT_OPENAI_CODEX_ACCESS_TOKEN"
_NAGIENT_CODEX_API_KEY_ENV = "NAGIENT_OPENAI_CODEX_API_KEY"
_CODEX_API_KEY_ENV = "CODEX_API_KEY"
_OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
_CODEX_HOME_ENV = "CODEX_HOME"
_OPENAI_CODEX_OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
_OPENAI_CODEX_OAUTH_AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
_OPENAI_CODEX_OAUTH_TOKEN_URL = "https://auth.openai.com/oauth/token"
_OPENAI_CODEX_OAUTH_DEFAULT_REDIRECT_URI = "http://127.0.0.1:1455/auth/callback"
_OPENAI_CODEX_OAUTH_SCOPES = (
    "openid",
    "profile",
    "email",
    "offline_access",
    "model.request",
    "api.model.read",
    "api.responses.write",
)


@dataclass(frozen=True)
class _CodexAuthCache:
    path: Path
    api_key: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class HttpProviderPlugin(BaseProviderPlugin):
    manifest: ProviderPluginManifest
    default_base_url: str
    default_secret_name: str | None = None
    auth_header_name: str = "Authorization"
    auth_header_format: str = "Bearer {token}"
    list_models_path: str = "/models"
    query_auth_parameter: str | None = None
    static_headers: dict[str, str] = field(default_factory=dict)
    http_client: JsonHttpClient = field(default_factory=JsonHttpClient)

    def validate_config(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> list[CheckIssue]:
        del secrets, credential
        issues: list[CheckIssue] = []
        auth_mode = _auth_mode(config, self.manifest.default_auth_mode)
        if auth_mode not in self.manifest.supported_auth_modes:
            issues.append(
                _issue(
                    "error",
                    "provider.unsupported_auth_mode",
                    provider_id,
                    (
                        f"Provider {provider_id!r} does not support auth mode "
                        f"{auth_mode!r}."
                    ),
                )
            )

        base_url = _string_config(config, "base_url")
        if base_url is not None and not base_url.startswith(("http://", "https://")):
            issues.append(
                _issue(
                    "error",
                    "provider.invalid_base_url",
                    provider_id,
                    f"Provider {provider_id!r} must define a valid base_url.",
                )
            )

        models_path = _string_config(config, "models_path")
        if models_path is not None and not models_path.startswith("/"):
            issues.append(
                _issue(
                    "error",
                    "provider.invalid_models_path",
                    provider_id,
                    f"Provider {provider_id!r} must use a models_path starting with '/'.",
                )
            )

        timeout_seconds = config.get("timeout_seconds")
        if timeout_seconds is not None and (
            not isinstance(timeout_seconds, int) or timeout_seconds <= 0
        ):
            issues.append(
                _issue(
                    "error",
                    "provider.invalid_timeout",
                    provider_id,
                    f"Provider {provider_id!r} must use a positive timeout_seconds value.",
                )
            )

        if auth_mode == "api_key":
            secret_name = self._secret_name(config)
            if secret_name is None:
                issues.append(
                    _issue(
                        "error",
                        "provider.missing_secret_ref",
                        provider_id,
                        (
                            f"Provider {provider_id!r} must define api_key_secret or rely "
                            "on a built-in default secret name."
                        ),
                    )
                )
        return issues

    def auth_status(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> ProviderAuthStatus:
        auth_mode = _auth_mode(config, self.manifest.default_auth_mode)
        if auth_mode == "none":
            return ProviderAuthStatus(
                authenticated=True,
                auth_mode="none",
                status="ready",
                message="No credentials are required for this provider profile.",
            )

        if auth_mode == "api_key":
            secret_name = self._secret_name(config)
            if secret_name is None:
                return ProviderAuthStatus(
                    authenticated=False,
                    auth_mode="api_key",
                    status="missing_config",
                    message="The provider profile does not define an API key secret name.",
                    issues=[
                        _issue(
                            "warning",
                            "provider.missing_secret_ref",
                            provider_id,
                            (
                                f"Provider {provider_id!r} is enabled but does not define "
                                "api_key_secret."
                            ),
                        )
                    ],
                )
            if secret_name not in secrets:
                return ProviderAuthStatus(
                    authenticated=False,
                    auth_mode="api_key",
                    status="missing_credentials",
                    message=f"Secret {secret_name!r} is not present in secrets.env.",
                    issues=[
                        _issue(
                            "warning",
                            "provider.secret_not_found",
                            provider_id,
                            (
                                f"Provider {provider_id!r} expects secret "
                                f"{secret_name!r}, but it is missing."
                            ),
                            hint=(
                                "Add the secret to secrets.env or run "
                                f"`nagient auth login {provider_id}`."
                            ),
                        )
                    ],
                )
            return ProviderAuthStatus(
                authenticated=True,
                auth_mode="api_key",
                status="ready",
                message=f"Secret {secret_name!r} is configured.",
            )

        if auth_mode == "stored_token":
            token = _token_from_credential(credential)
            if not token:
                return ProviderAuthStatus(
                    authenticated=False,
                    auth_mode="stored_token",
                    status="missing_credentials",
                    message="No stored access token was found for this provider.",
                    issues=[
                        _issue(
                            "warning",
                            "provider.token_not_found",
                            provider_id,
                            (
                                f"Provider {provider_id!r} expects a stored token, but no "
                                "credential record is present."
                            ),
                            hint=(
                                f"Run `nagient auth login {provider_id} --token <token>` "
                                "or complete a browser login session."
                            ),
                        )
                    ],
                )
            return ProviderAuthStatus(
                authenticated=True,
                auth_mode="stored_token",
                status="ready",
                message="A stored token is available in the credential store.",
            )

        return ProviderAuthStatus(
            authenticated=False,
            auth_mode=auth_mode,
            status="unsupported",
            message=f"Auth mode {auth_mode!r} is not implemented by this provider.",
            issues=[
                _issue(
                    "warning",
                    "provider.auth_not_implemented",
                    provider_id,
                    (
                        f"Provider {provider_id!r} uses auth mode {auth_mode!r}, which "
                        "is not implemented yet."
                    ),
                )
            ],
        )

    def begin_login(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> AuthSessionState:
        del config, secrets, credential
        return AuthSessionState(
            session_id=str(uuid.uuid4()),
            provider_id=provider_id,
            plugin_id=self.manifest.plugin_id,
            auth_mode="browser_callback",
            status="unsupported",
            submission_mode="callback_url",
            instructions=[
                (
                    "This built-in provider currently supports API keys or stored tokens, "
                    "not a vendor-managed browser login flow."
                ),
                "Use `nagient auth login <provider> --api-key ...` or `--token ...` instead.",
            ],
        )

    def complete_login(
        self,
        provider_id: str,
        config: Mapping[str, object],
        credential: CredentialRecord | None,
        session: AuthSessionState,
        *,
        callback_url: str | None = None,
        code: str | None = None,
    ) -> CredentialRecord:
        del provider_id, config, credential, session, callback_url, code
        raise NotImplementedError

    def healthcheck(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> list[CheckIssue]:
        try:
            self.list_models(provider_id, config, secrets, credential)
        except Exception as exc:
            return [
                _issue(
                    "warning",
                    "provider.remote_check_failed",
                    provider_id,
                    f"Remote verification failed for provider {provider_id!r}: {exc}",
                )
            ]
        return []

    def list_models(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> list[ProviderModel]:
        headers, query = self._build_request_auth(config, secrets, credential)
        payload = self.http_client.get_json(
            self._models_url(config),
            headers=headers,
            query=query,
            timeout=_timeout_seconds(config),
        )
        return _parse_data_models(payload, provider_id)

    def generate_message(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
        *,
        message: str,
        system_prompt: str | None = None,
    ) -> str:
        bearer_token = self._resolve_bearer_token(config, secrets, credential)
        if not bearer_token:
            raise ValueError(
                "Chat for openai-codex requires either OAuth credentials or an API key."
            )
        model = _require_model(provider_id, config)
        messages: list[dict[str, object]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        payload = self.http_client.post_json(
            self._chat_url(config),
            {
                "model": model,
                "messages": messages,
                "stream": False,
            },
            headers={"Authorization": f"Bearer {bearer_token}"},
            timeout=_timeout_seconds(config),
        )
        return _parse_openai_chat_message(payload, provider_id)

    def generate_message(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
        *,
        message: str,
        system_prompt: str | None = None,
    ) -> str:
        model = _require_model(provider_id, config)
        headers, query = self._build_request_auth(config, secrets, credential)
        messages: list[dict[str, object]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        payload = self.http_client.post_json(
            self._chat_url(config),
            {
                "model": model,
                "messages": messages,
                "stream": False,
            },
            headers=headers,
            query=query,
            timeout=_timeout_seconds(config),
        )
        return _parse_openai_chat_message(payload, provider_id)

    def _secret_name(self, config: Mapping[str, object]) -> str | None:
        secret_name = _string_config(config, "api_key_secret")
        if secret_name is not None:
            return secret_name
        return self.default_secret_name

    def _models_url(self, config: Mapping[str, object]) -> str:
        base_url = _string_config(config, "base_url") or self.default_base_url
        models_path = _string_config(config, "models_path") or self.list_models_path
        return f"{base_url.rstrip('/')}{models_path}"

    def _chat_url(self, config: Mapping[str, object]) -> str:
        base_url = _string_config(config, "base_url") or self.default_base_url
        chat_path = _string_config(config, "chat_path") or "/chat/completions"
        return f"{base_url.rstrip('/')}{chat_path}"

    def _build_request_auth(
        self,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> tuple[dict[str, str], dict[str, str]]:
        auth_mode = _auth_mode(config, self.manifest.default_auth_mode)
        headers = dict(self.static_headers)
        query: dict[str, str] = {}

        if auth_mode == "none":
            return headers, query

        token = ""
        if auth_mode == "api_key":
            secret_name = self._secret_name(config)
            if secret_name is None or secret_name not in secrets:
                raise ValueError("Missing API key secret for provider request.")
            token = secrets[secret_name]
        elif auth_mode == "stored_token":
            token = _token_from_credential(credential)
            if not token:
                raise ValueError("Missing stored token for provider request.")

        if self.query_auth_parameter:
            query[self.query_auth_parameter] = token
            return headers, query

        headers[self.auth_header_name] = self.auth_header_format.format(token=token)
        return headers, query


@dataclass(frozen=True)
class AnthropicProviderPlugin(HttpProviderPlugin):
    def list_models(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> list[ProviderModel]:
        headers, query = self._build_request_auth(config, secrets, credential)
        headers["anthropic-version"] = str(config.get("api_version", "2023-06-01"))
        payload = self.http_client.get_json(
            self._models_url(config),
            headers=headers,
            query=query,
            timeout=_timeout_seconds(config),
        )
        return _parse_data_models(payload, provider_id)

    def generate_message(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
        *,
        message: str,
        system_prompt: str | None = None,
    ) -> str:
        model = _require_model(provider_id, config)
        headers, query = self._build_request_auth(config, secrets, credential)
        headers["anthropic-version"] = str(config.get("api_version", "2023-06-01"))
        payload: dict[str, object] = {
            "model": model,
            "max_tokens": int(config.get("max_tokens", 1024)),
            "messages": [{"role": "user", "content": message}],
        }
        if system_prompt:
            payload["system"] = system_prompt
        response = self.http_client.post_json(
            self._chat_url(config),
            payload,
            headers=headers,
            query=query,
            timeout=_timeout_seconds(config),
        )
        return _parse_anthropic_message(response, provider_id)

    def _chat_url(self, config: Mapping[str, object]) -> str:
        base_url = _string_config(config, "base_url") or self.default_base_url
        chat_path = _string_config(config, "chat_path") or "/messages"
        return f"{base_url.rstrip('/')}{chat_path}"


@dataclass(frozen=True)
class GeminiProviderPlugin(HttpProviderPlugin):
    def list_models(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> list[ProviderModel]:
        headers, query = self._build_request_auth(config, secrets, credential)
        payload = self.http_client.get_json(
            self._models_url(config),
            headers=headers,
            query=query,
            timeout=_timeout_seconds(config),
        )
        if not isinstance(payload, dict):
            raise ProviderHttpError(
                f"Provider {provider_id!r} returned an unexpected Gemini response."
            )
        raw_models = payload.get("models", [])
        if not isinstance(raw_models, list):
            raise ProviderHttpError(
                f"Provider {provider_id!r} returned an invalid Gemini model list."
            )
        models: list[ProviderModel] = []
        for item in raw_models:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("name", "")).strip()
            if not model_id:
                continue
            display_name = str(item.get("displayName", model_id))
            models.append(
                ProviderModel(
                    model_id=model_id,
                    display_name=display_name,
                    metadata=dict(item),
                )
            )
        return models

    def generate_message(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
        *,
        message: str,
        system_prompt: str | None = None,
    ) -> str:
        model = _require_model(provider_id, config)
        headers, query = self._build_request_auth(config, secrets, credential)
        payload: dict[str, object] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": message}],
                }
            ]
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        response = self.http_client.post_json(
            self._chat_url(config, model),
            payload,
            headers=headers,
            query=query,
            timeout=_timeout_seconds(config),
        )
        return _parse_gemini_message(response, provider_id)

    def _chat_url(self, config: Mapping[str, object], model: str) -> str:
        base_url = _string_config(config, "base_url") or self.default_base_url
        return f"{base_url.rstrip('/')}/models/{model}:generateContent"


@dataclass(frozen=True)
class OllamaProviderPlugin(HttpProviderPlugin):
    def list_models(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> list[ProviderModel]:
        headers, query = self._build_request_auth(config, secrets, credential)
        payload = self.http_client.get_json(
            self._models_url(config),
            headers=headers,
            query=query,
            timeout=_timeout_seconds(config),
        )
        if not isinstance(payload, dict):
            raise ProviderHttpError(
                f"Provider {provider_id!r} returned an unexpected Ollama response."
            )
        raw_models = payload.get("models", [])
        if not isinstance(raw_models, list):
            raise ProviderHttpError(
                f"Provider {provider_id!r} returned an invalid Ollama model list."
            )
        models: list[ProviderModel] = []
        for item in raw_models:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("name", "")).strip()
            if not model_id:
                continue
            models.append(
                ProviderModel(
                    model_id=model_id,
                    display_name=model_id,
                    metadata=dict(item),
                )
            )
        return models

    def generate_message(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
        *,
        message: str,
        system_prompt: str | None = None,
    ) -> str:
        model = _require_model(provider_id, config)
        headers, query = self._build_request_auth(config, secrets, credential)
        messages: list[dict[str, object]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        response = self.http_client.post_json(
            self._chat_url(config),
            {
                "model": model,
                "messages": messages,
                "stream": False,
            },
            headers=headers,
            query=query,
            timeout=_timeout_seconds(config),
        )
        return _parse_ollama_message(response, provider_id)

    def _chat_url(self, config: Mapping[str, object]) -> str:
        base_url = _string_config(config, "base_url") or self.default_base_url
        chat_path = _string_config(config, "chat_path") or "/api/chat"
        return f"{base_url.rstrip('/')}{chat_path}"


@dataclass(frozen=True)
class CredentialFileProviderPlugin(BaseProviderPlugin):
    manifest: ProviderPluginManifest
    credential_label: str

    def validate_config(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> list[CheckIssue]:
        del secrets, credential
        issues: list[CheckIssue] = []
        auth_mode = _auth_mode(config, self.manifest.default_auth_mode)
        if auth_mode not in self.manifest.supported_auth_modes:
            issues.append(
                _issue(
                    "error",
                    "provider.unsupported_auth_mode",
                    provider_id,
                    (
                        f"Provider {provider_id!r} does not support auth mode "
                        f"{auth_mode!r}."
                    ),
                )
            )
        if auth_mode == "credential_file":
            credential_file = _string_config(config, "credential_file")
            if credential_file is None:
                issues.append(
                    _issue(
                        "error",
                        "provider.missing_credential_file",
                        provider_id,
                        (
                            f"Provider {provider_id!r} must define credential_file when "
                            "using credential_file auth."
                        ),
                    )
                )
        return issues

    def auth_status(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> ProviderAuthStatus:
        del secrets
        auth_mode = _auth_mode(config, self.manifest.default_auth_mode)
        if auth_mode == "credential_file":
            credential_file = _string_config(config, "credential_file")
            if credential_file is None:
                return ProviderAuthStatus(
                    authenticated=False,
                    auth_mode="credential_file",
                    status="missing_config",
                    message="credential_file is not configured.",
                    issues=[
                        _issue(
                            "warning",
                            "provider.credential_file_missing",
                            provider_id,
                            (
                                f"Provider {provider_id!r} does not define "
                                "credential_file."
                            ),
                        )
                    ],
                )
            if not Path(credential_file).expanduser().exists():
                return ProviderAuthStatus(
                    authenticated=False,
                    auth_mode="credential_file",
                    status="missing_credentials",
                    message=f"Credential file {credential_file!r} does not exist.",
                    issues=[
                        _issue(
                            "warning",
                            "provider.credential_file_not_found",
                            provider_id,
                            (
                                f"Provider {provider_id!r} references credential_file "
                                f"{credential_file!r}, but it does not exist."
                            ),
                        )
                    ],
                )
            return ProviderAuthStatus(
                authenticated=True,
                auth_mode="credential_file",
                status="ready",
                message=(
                    f"{self.credential_label} credential_file is configured at "
                    f"{credential_file!r}."
                ),
            )

        if auth_mode == "stored_token":
            token = _token_from_credential(credential)
            if not token:
                return ProviderAuthStatus(
                    authenticated=False,
                    auth_mode="stored_token",
                    status="missing_credentials",
                    message="No stored token was found for this provider.",
                    issues=[
                        _issue(
                            "warning",
                            "provider.token_not_found",
                            provider_id,
                            (
                                f"Provider {provider_id!r} expects a stored token, but no "
                                "credential record is present."
                            ),
                        )
                    ],
                )
            return ProviderAuthStatus(
                authenticated=True,
                auth_mode="stored_token",
                status="ready",
                message="A stored token is available in the credential store.",
            )

        return ProviderAuthStatus(
            authenticated=False,
            auth_mode=auth_mode,
            status="unsupported",
            message=f"Auth mode {auth_mode!r} is not implemented by this provider.",
        )

    def begin_login(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> AuthSessionState:
        del config, secrets, credential
        return AuthSessionState(
            session_id=str(uuid.uuid4()),
            provider_id=provider_id,
            plugin_id=self.manifest.plugin_id,
            auth_mode="external_credentials",
            status="manual",
            submission_mode="none",
            instructions=[
                (
                    f"This provider expects {self.credential_label} credentials to be "
                    "mounted or written to a file path configured in config.toml."
                ),
                "Direct browser login is not implemented for this built-in provider.",
            ],
        )

    def complete_login(
        self,
        provider_id: str,
        config: Mapping[str, object],
        credential: CredentialRecord | None,
        session: AuthSessionState,
        *,
        callback_url: str | None = None,
        code: str | None = None,
    ) -> CredentialRecord:
        del provider_id, config, credential, session, callback_url, code
        raise NotImplementedError


@dataclass(frozen=True)
class OpenAICodexProviderPlugin(BaseProviderPlugin):
    manifest: ProviderPluginManifest
    default_base_url: str
    default_secret_name: str = "CODEX_API_KEY"
    default_auth_file: str = "~/.codex/auth.json"
    login_url: str = _OPENAI_CODEX_OAUTH_AUTHORIZE_URL
    token_url: str = _OPENAI_CODEX_OAUTH_TOKEN_URL
    client_id: str = _OPENAI_CODEX_OAUTH_CLIENT_ID
    default_redirect_uri: str = _OPENAI_CODEX_OAUTH_DEFAULT_REDIRECT_URI
    http_client: JsonHttpClient = field(default_factory=JsonHttpClient)

    def validate_config(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> list[CheckIssue]:
        del secrets, credential
        issues: list[CheckIssue] = []
        auth_mode = _auth_mode(config, self.manifest.default_auth_mode)
        if auth_mode not in self.manifest.supported_auth_modes:
            issues.append(
                _issue(
                    "error",
                    "provider.unsupported_auth_mode",
                    provider_id,
                    (
                        f"Provider {provider_id!r} does not support auth mode "
                        f"{auth_mode!r}."
                    ),
                )
            )

        base_url = _string_config(config, "base_url")
        if base_url is not None and not base_url.startswith(("http://", "https://")):
            issues.append(
                _issue(
                    "error",
                    "provider.invalid_base_url",
                    provider_id,
                    f"Provider {provider_id!r} must define a valid base_url.",
                )
            )

        models_path = _string_config(config, "models_path")
        if models_path is not None and not models_path.startswith("/"):
            issues.append(
                _issue(
                    "error",
                    "provider.invalid_models_path",
                    provider_id,
                    f"Provider {provider_id!r} must use a models_path starting with '/'.",
                )
            )

        timeout_seconds = config.get("timeout_seconds")
        if timeout_seconds is not None and (
            not isinstance(timeout_seconds, int) or timeout_seconds <= 0
        ):
            issues.append(
                _issue(
                    "error",
                    "provider.invalid_timeout",
                    provider_id,
                    f"Provider {provider_id!r} must use a positive timeout_seconds value.",
                )
            )

        configured_auth_file = _string_config(config, "auth_file")
        if auth_mode == "codex_auth_file" and configured_auth_file:
            auth_file = Path(configured_auth_file).expanduser()
            if not auth_file.exists():
                issues.append(
                    _issue(
                        "warning",
                        "provider.codex_auth_file_missing",
                        provider_id,
                        (
                            f"Provider {provider_id!r} references auth_file "
                            f"{configured_auth_file!r}, but it does not exist yet."
                        ),
                        hint=(
                            "Run `codex login` and retry, or set "
                            f"{_CODEX_AUTH_FILE_ENV} to a valid file path."
                        ),
                    )
                )

        redirect_uri = self._redirect_uri(config)
        if auth_mode == "oauth_browser" and redirect_uri is not None:
            if not redirect_uri.startswith(("http://", "https://")):
                issues.append(
                    _issue(
                        "error",
                        "provider.invalid_redirect_uri",
                        provider_id,
                        f"Provider {provider_id!r} must define a valid redirect_uri.",
                    )
                )

        return issues

    def auth_status(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> ProviderAuthStatus:
        auth_mode = _auth_mode(config, self.manifest.default_auth_mode)
        if auth_mode == "api_key":
            return self._api_key_auth_status(provider_id, config, secrets, credential)
        if auth_mode == "oauth_browser":
            return self._oauth_browser_auth_status(provider_id, credential)
        if auth_mode == "stored_token":
            return self._stored_token_auth_status(provider_id, config, credential)
        if auth_mode == "codex_auth_file":
            return self._codex_auth_file_status(provider_id, config, credential)
        return ProviderAuthStatus(
            authenticated=False,
            auth_mode=auth_mode,
            status="unsupported",
            message=f"Auth mode {auth_mode!r} is not implemented by this provider.",
            issues=[
                _issue(
                    "warning",
                    "provider.auth_not_implemented",
                    provider_id,
                    (
                        f"Provider {provider_id!r} uses auth mode {auth_mode!r}, which "
                        "is not implemented yet."
                    ),
                )
            ],
        )

    def begin_login(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> AuthSessionState:
        del secrets, credential
        auth_mode = _auth_mode(config, self.manifest.default_auth_mode)
        if auth_mode == "codex_auth_file":
            auth_file = self._auth_file_path(config)
            return AuthSessionState(
                session_id=str(uuid.uuid4()),
                provider_id=provider_id,
                plugin_id=self.manifest.plugin_id,
                auth_mode="codex_auth_file",
                status="awaiting_user_action",
                submission_mode="none",
                authorization_url="https://chatgpt.com/codex",
                callback_url="https://auth.openai.com/codex/device",
                instructions=[
                    "Open the Codex sign-in page and complete ChatGPT login.",
                    (
                        "If Codex CLI is available, run `codex login` (or "
                        "`codex login --device-auth` on headless hosts)."
                    ),
                    f"Nagient checks Codex auth cache at {str(auth_file)!r}.",
                    (
                        "If CLI login is unavailable, set one of: "
                        f"{_CODEX_AUTH_FILE_ENV}, {_CODEX_ACCESS_TOKEN_ENV}, "
                        f"{_CODEX_API_KEY_ENV}, {_OPENAI_API_KEY_ENV}."
                    ),
                ],
                metadata={
                    "auth_file": str(auth_file),
                    "login_url": "https://chatgpt.com/codex",
                    "device_code_url": "https://auth.openai.com/codex/device",
                    "auth_file_env": _CODEX_AUTH_FILE_ENV,
                    "access_token_env": _CODEX_ACCESS_TOKEN_ENV,
                    "api_key_env": [
                        _NAGIENT_CODEX_API_KEY_ENV,
                        _CODEX_API_KEY_ENV,
                        _OPENAI_API_KEY_ENV,
                    ],
                },
            )

        session_id = str(uuid.uuid4())
        redirect_uri = self._redirect_uri(config)
        state = secretslib.token_urlsafe(32)
        verifier = _pkce_verifier()
        challenge = _pkce_challenge(verifier)
        scope = " ".join(_OPENAI_CODEX_OAUTH_SCOPES)
        authorization_url = self._authorization_url(
            redirect_uri=redirect_uri,
            state=state,
            code_challenge=challenge,
            scope=scope,
        )

        return AuthSessionState(
            session_id=session_id,
            provider_id=provider_id,
            plugin_id=self.manifest.plugin_id,
            auth_mode="oauth_browser",
            status="awaiting_user_action",
            submission_mode="callback_url",
            authorization_url=authorization_url,
            callback_url=redirect_uri,
            instructions=[
                "Open the authorization URL in your browser and sign in with ChatGPT.",
                "Approve Codex access for Nagient.",
                (
                    "If the browser redirects to a localhost URL, paste that full redirect "
                    "URL into `nagient auth complete ... --callback-url`."
                ),
                "If only an authorization code is available, pass it with `--code`.",
            ],
            metadata={
                "oauth_authorize_url": self.login_url,
                "oauth_token_url": self.token_url,
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "state": state,
                "code_verifier": verifier,
                "scope": scope,
            },
        )

    def complete_login(
        self,
        provider_id: str,
        config: Mapping[str, object],
        credential: CredentialRecord | None,
        session: AuthSessionState,
        *,
        callback_url: str | None = None,
        code: str | None = None,
    ) -> CredentialRecord:
        auth_mode = _auth_mode(config, self.manifest.default_auth_mode)
        if auth_mode == "oauth_browser":
            return self._complete_oauth_browser_login(
                provider_id,
                credential,
                session,
                callback_url=callback_url,
                code=code,
            )

        del credential, session
        data: dict[str, object] = {}

        manual_token = (code or callback_url or "").strip()
        if manual_token:
            data["access_token"] = manual_token

        cache = _load_codex_auth_cache(self._auth_file_path(config))
        if cache.error:
            raise ValueError(f"Cannot read Codex auth cache: {cache.error}")
        if cache.api_key:
            data.setdefault("api_key", cache.api_key)
        if cache.access_token:
            data.setdefault("access_token", cache.access_token)
        if cache.refresh_token:
            data.setdefault("refresh_token", cache.refresh_token)
        if cache.path.exists():
            data.setdefault("auth_file", str(cache.path))

        env_access_name, env_access_token = _first_present_env((_CODEX_ACCESS_TOKEN_ENV,))
        if env_access_token:
            data.setdefault("access_token", env_access_token)
            data.setdefault("access_token_env", env_access_name)

        env_api_name, env_api_key = _first_present_env(
            (_NAGIENT_CODEX_API_KEY_ENV, _CODEX_API_KEY_ENV, _OPENAI_API_KEY_ENV)
        )
        if env_api_key:
            data.setdefault("api_key", env_api_key)
            data.setdefault("api_key_env", env_api_name)

        if not data:
            raise ValueError(
                "No Codex credentials were found. Run `codex login`, provide `--code`, "
                "or set NAGIENT_OPENAI_CODEX_ACCESS_TOKEN / CODEX_API_KEY."
            )

        return CredentialRecord(
            provider_id=provider_id,
            plugin_id=self.manifest.plugin_id,
            auth_mode=auth_mode,
            issued_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            data=data,
        )

    def list_models(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> list[ProviderModel]:
        bearer_token = self._resolve_bearer_token(config, secrets, credential)
        if not bearer_token:
            raise ValueError(
                "Model discovery for openai-codex requires either OAuth credentials or an "
                "API key. Run `nagient auth login openai-codex` or set CODEX_API_KEY."
            )
        payload = self.http_client.get_json(
            self._models_url(config),
            headers={"Authorization": f"Bearer {bearer_token}"},
            timeout=_timeout_seconds(config),
        )
        return _parse_data_models(payload, provider_id)

    def _oauth_browser_auth_status(
        self,
        provider_id: str,
        credential: CredentialRecord | None,
    ) -> ProviderAuthStatus:
        access_token = _credential_field(credential, "access_token")
        refresh_token = _credential_field(credential, "refresh_token")
        expires_at = _credential_field(credential, "expires_at")
        if access_token and not _is_expired(expires_at):
            return ProviderAuthStatus(
                authenticated=True,
                auth_mode="oauth_browser",
                status="ready",
                message="Browser login is configured and access token is available.",
            )
        if refresh_token:
            return ProviderAuthStatus(
                authenticated=True,
                auth_mode="oauth_browser",
                status="ready",
                message="Browser login is configured and refresh token is available.",
            )
        return ProviderAuthStatus(
            authenticated=False,
            auth_mode="oauth_browser",
            status="missing_credentials",
            message="No completed browser login session was found for this provider.",
            issues=[
                _issue(
                    "warning",
                    "provider.oauth_login_required",
                    provider_id,
                    (
                        f"Provider {provider_id!r} expects a browser login session, but no "
                        "stored OAuth credential was found."
                    ),
                    hint=(
                        f"Run `nagient auth login {provider_id}` and complete the URL-based "
                        "login flow."
                    ),
                )
            ],
        )

    def _api_key_auth_status(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> ProviderAuthStatus:
        secret_name = self._secret_name(config)
        secret_value = secrets.get(secret_name, "")
        if secret_value.strip():
            return ProviderAuthStatus(
                authenticated=True,
                auth_mode="api_key",
                status="ready",
                message=f"Secret {secret_name!r} is configured.",
            )

        env_name, env_value = _first_present_env(
            (_NAGIENT_CODEX_API_KEY_ENV, _CODEX_API_KEY_ENV, _OPENAI_API_KEY_ENV)
        )
        if env_value:
            return ProviderAuthStatus(
                authenticated=True,
                auth_mode="api_key",
                status="ready",
                message=f"API key is available via environment variable {env_name!r}.",
            )

        cache = _load_codex_auth_cache(self._auth_file_path(config))
        if cache.error:
            return ProviderAuthStatus(
                authenticated=False,
                auth_mode="api_key",
                status="missing_credentials",
                message=f"Cannot read Codex auth cache: {cache.error}",
                issues=[
                    _issue(
                        "warning",
                        "provider.codex_auth_cache_invalid",
                        provider_id,
                        f"Provider {provider_id!r} cannot parse Codex auth cache.",
                        hint=(
                            "Fix the auth cache file or configure CODEX_API_KEY / "
                            "OPENAI_API_KEY instead."
                        ),
                    )
                ],
            )
        if cache.api_key:
            return ProviderAuthStatus(
                authenticated=True,
                auth_mode="api_key",
                status="ready",
                message=f"Codex auth cache at {str(cache.path)!r} contains OPENAI_API_KEY.",
            )

        credential_api_key = _credential_field(credential, "api_key")
        if credential_api_key:
            return ProviderAuthStatus(
                authenticated=True,
                auth_mode="api_key",
                status="ready",
                message="An API key is available in the credential store.",
            )

        return ProviderAuthStatus(
            authenticated=False,
            auth_mode="api_key",
            status="missing_credentials",
            message=(
                f"Secret {secret_name!r} is missing and no fallback API key was found."
            ),
            issues=[
                _issue(
                    "warning",
                    "provider.secret_not_found",
                    provider_id,
                    (
                        f"Provider {provider_id!r} expects API key secret {secret_name!r}, "
                        "but it is missing."
                    ),
                    hint=(
                        f"Run `nagient auth login {provider_id} --api-key ...`, add "
                        f"{secret_name} to secrets.env, or export CODEX_API_KEY."
                    ),
                )
            ],
        )

    def _stored_token_auth_status(
        self,
        provider_id: str,
        config: Mapping[str, object],
        credential: CredentialRecord | None,
    ) -> ProviderAuthStatus:
        token = _token_from_credential(credential)
        if token:
            return ProviderAuthStatus(
                authenticated=True,
                auth_mode="stored_token",
                status="ready",
                message="A stored token is available in the credential store.",
            )

        env_name, env_token = _first_present_env((_CODEX_ACCESS_TOKEN_ENV,))
        if env_token:
            return ProviderAuthStatus(
                authenticated=True,
                auth_mode="stored_token",
                status="ready",
                message=f"A token is available via environment variable {env_name!r}.",
            )

        cache = _load_codex_auth_cache(self._auth_file_path(config))
        if cache.error:
            return ProviderAuthStatus(
                authenticated=False,
                auth_mode="stored_token",
                status="missing_credentials",
                message=f"Cannot read Codex auth cache: {cache.error}",
                issues=[
                    _issue(
                        "warning",
                        "provider.codex_auth_cache_invalid",
                        provider_id,
                        f"Provider {provider_id!r} cannot parse Codex auth cache.",
                    )
                ],
            )

        if cache.access_token:
            return ProviderAuthStatus(
                authenticated=True,
                auth_mode="stored_token",
                status="ready",
                message=f"Codex auth cache at {str(cache.path)!r} contains an access token.",
            )

        return ProviderAuthStatus(
            authenticated=False,
            auth_mode="stored_token",
            status="missing_credentials",
            message="No stored token was found for this provider.",
            issues=[
                _issue(
                    "warning",
                    "provider.token_not_found",
                    provider_id,
                    (
                        f"Provider {provider_id!r} expects a stored token, but no token "
                        "was found in credential store, env, or Codex auth cache."
                    ),
                    hint=(
                        "Run `codex login` and reuse ~/.codex/auth.json, export "
                        "NAGIENT_OPENAI_CODEX_ACCESS_TOKEN, or use `nagient auth login "
                        f"{provider_id} --token ...`."
                    ),
                )
            ],
        )

    def _codex_auth_file_status(
        self,
        provider_id: str,
        config: Mapping[str, object],
        credential: CredentialRecord | None,
    ) -> ProviderAuthStatus:
        token = _token_from_credential(credential)
        if token:
            return ProviderAuthStatus(
                authenticated=True,
                auth_mode="codex_auth_file",
                status="ready",
                message="Credential store contains a reusable token for this provider.",
            )

        env_access_name, env_access_token = _first_present_env((_CODEX_ACCESS_TOKEN_ENV,))
        if env_access_token:
            return ProviderAuthStatus(
                authenticated=True,
                auth_mode="codex_auth_file",
                status="ready",
                message=f"Token is available via environment variable {env_access_name!r}.",
            )

        env_api_name, env_api_key = _first_present_env(
            (_NAGIENT_CODEX_API_KEY_ENV, _CODEX_API_KEY_ENV, _OPENAI_API_KEY_ENV)
        )
        if env_api_key:
            return ProviderAuthStatus(
                authenticated=True,
                auth_mode="codex_auth_file",
                status="ready",
                message=f"API key is available via environment variable {env_api_name!r}.",
            )

        cache = _load_codex_auth_cache(self._auth_file_path(config))
        if cache.error:
            return ProviderAuthStatus(
                authenticated=False,
                auth_mode="codex_auth_file",
                status="missing_credentials",
                message=f"Cannot read Codex auth cache: {cache.error}",
                issues=[
                    _issue(
                        "warning",
                        "provider.codex_auth_cache_invalid",
                        provider_id,
                        (
                            f"Provider {provider_id!r} could not parse Codex auth cache at "
                            f"{str(cache.path)!r}."
                        ),
                        hint=(
                            "Re-run `codex login` to refresh auth cache, or set "
                            "NAGIENT_OPENAI_CODEX_AUTH_FILE to a valid file."
                        ),
                    )
                ],
            )

        if cache.api_key:
            return ProviderAuthStatus(
                authenticated=True,
                auth_mode="codex_auth_file",
                status="ready",
                message=f"Codex auth cache at {str(cache.path)!r} contains OPENAI_API_KEY.",
            )
        if cache.access_token:
            return ProviderAuthStatus(
                authenticated=True,
                auth_mode="codex_auth_file",
                status="ready",
                message=f"Codex auth cache at {str(cache.path)!r} contains access token.",
            )

        return ProviderAuthStatus(
            authenticated=False,
            auth_mode="codex_auth_file",
            status="missing_credentials",
            message=(
                f"No Codex credentials were found at {str(cache.path)!r}."
            ),
            issues=[
                _issue(
                    "warning",
                    "provider.codex_auth_cache_missing",
                    provider_id,
                    (
                        f"Provider {provider_id!r} expects Codex auth cache, but file "
                        f"{str(cache.path)!r} is missing or empty."
                    ),
                    hint=(
                        "Run `codex login` or `codex login --device-auth`, then rerun "
                        f"`nagient auth status {provider_id}`."
                    ),
                )
            ],
        )

    def _secret_name(self, config: Mapping[str, object]) -> str:
        secret_name = _string_config(config, "api_key_secret")
        if secret_name is not None:
            return secret_name
        return self.default_secret_name

    def _authorization_url(
        self,
        *,
        redirect_uri: str,
        state: str,
        code_challenge: str,
        scope: str,
    ) -> str:
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "scope": scope,
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "originator": "nagient",
                "codex_cli_simplified_flow": "true",
            }
        )
        return f"{self.login_url}?{query}"

    def _redirect_uri(self, config: Mapping[str, object]) -> str:
        redirect_uri = _string_config(config, "redirect_uri")
        if redirect_uri:
            return redirect_uri
        legacy_redirect_uri = _string_config(config, "auth_file")
        if legacy_redirect_uri and legacy_redirect_uri.startswith(("http://", "https://")):
            return legacy_redirect_uri
        return self.default_redirect_uri

    def _models_url(self, config: Mapping[str, object]) -> str:
        base_url = _string_config(config, "base_url") or self.default_base_url
        models_path = _string_config(config, "models_path") or "/models"
        return f"{base_url.rstrip('/')}{models_path}"

    def _chat_url(self, config: Mapping[str, object]) -> str:
        base_url = _string_config(config, "base_url") or self.default_base_url
        chat_path = _string_config(config, "chat_path") or "/chat/completions"
        return f"{base_url.rstrip('/')}{chat_path}"

    def _auth_file_path(self, config: Mapping[str, object]) -> Path:
        configured_auth_file = _string_config(config, "auth_file")
        if configured_auth_file:
            return Path(configured_auth_file).expanduser()

        env_auth_file = os.environ.get(_CODEX_AUTH_FILE_ENV, "").strip()
        if env_auth_file:
            return Path(env_auth_file).expanduser()

        codex_home = os.environ.get(_CODEX_HOME_ENV, "").strip()
        if codex_home:
            return Path(codex_home).expanduser() / "auth.json"

        return Path(self.default_auth_file).expanduser()

    def _resolve_api_key(
        self,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> str:
        secret_name = self._secret_name(config)
        if secret_name in secrets and secrets[secret_name].strip():
            return secrets[secret_name].strip()

        env_name, env_value = _first_present_env(
            (_NAGIENT_CODEX_API_KEY_ENV, _CODEX_API_KEY_ENV, _OPENAI_API_KEY_ENV)
        )
        if env_name and env_value:
            return env_value

        credential_api_key = _credential_field(credential, "api_key")
        if credential_api_key:
            return credential_api_key

        cache = _load_codex_auth_cache(self._auth_file_path(config))
        if cache.api_key:
            return cache.api_key
        return ""

    def _resolve_bearer_token(
        self,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> str:
        api_key = self._resolve_api_key(config, secrets, credential)
        if api_key:
            return api_key
        access_token = _credential_field(credential, "access_token")
        if access_token:
            return access_token
        return ""

    def _complete_oauth_browser_login(
        self,
        provider_id: str,
        credential: CredentialRecord | None,
        session: AuthSessionState,
        *,
        callback_url: str | None,
        code: str | None,
    ) -> CredentialRecord:
        del credential
        parsed = _parse_oauth_callback(callback_url or "")
        authorization_code = (code or parsed.get("code") or "").strip()
        if not authorization_code:
            raise ValueError(
                "No authorization code was provided. Pass --callback-url with the full "
                "redirect URL or provide --code explicitly."
            )

        expected_state = str(session.metadata.get("state", "")).strip()
        received_state = parsed.get("state", "").strip()
        if expected_state and received_state and expected_state != received_state:
            raise ValueError("OAuth state mismatch. Start the login flow again.")

        code_verifier = str(session.metadata.get("code_verifier", "")).strip()
        redirect_uri = (
            str(session.metadata.get("redirect_uri", "")).strip()
            or self.default_redirect_uri
        )
        token_payload = self.http_client.post_form_json(
            self.token_url,
            {
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "code": authorization_code,
                "code_verifier": code_verifier,
            },
            timeout=30.0,
        )
        if not isinstance(token_payload, dict):
            raise ValueError("OpenAI OAuth token exchange returned an invalid payload.")

        access_token = _as_string(token_payload.get("access_token"))
        refresh_token = _as_string(token_payload.get("refresh_token"))
        if not access_token and not refresh_token:
            raise ValueError("OpenAI OAuth token exchange did not return usable credentials.")

        expires_in = token_payload.get("expires_in")
        expires_at = _expiry_timestamp(expires_in)
        data: dict[str, object] = {}
        if access_token:
            data["access_token"] = access_token
        if refresh_token:
            data["refresh_token"] = refresh_token
        if expires_at:
            data["expires_at"] = expires_at
        scope = _as_string(token_payload.get("scope"))
        if scope:
            data["scope"] = scope
        id_token = _as_string(token_payload.get("id_token"))
        if id_token:
            data["id_token"] = id_token
            subject = _jwt_subject(id_token)
            if subject:
                data["subject"] = subject

        return CredentialRecord(
            provider_id=provider_id,
            plugin_id=self.manifest.plugin_id,
            auth_mode="oauth_browser",
            issued_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            expires_at=expires_at or None,
            data=data,
        )


def builtin_providers() -> list[LoadedProviderPlugin]:
    providers: list[BaseProviderPlugin] = [
        HttpProviderPlugin(
            manifest=ProviderPluginManifest(
                plugin_id="builtin.openai",
                display_name="OpenAI API",
                version="0.1.0",
                family="openai",
                entrypoint="<builtin>",
                supported_auth_modes=["api_key", "stored_token"],
                default_auth_mode="api_key",
                capabilities=["list_models", "chat", "api_key_auth", "stored_token_auth"],
                required_config=[],
                optional_config=[
                    "auth",
                    "api_key_secret",
                    "base_url",
                    "model",
                    "models_path",
                    "chat_path",
                    "organization",
                    "timeout_seconds",
                ],
                secret_config=["api_key_secret"],
                credential_fields=["access_token", "refresh_token", "expires_at"],
            ),
            default_base_url="https://api.openai.com/v1",
            default_secret_name="OPENAI_API_KEY",
        ),
        OpenAICodexProviderPlugin(
            manifest=ProviderPluginManifest(
                plugin_id="builtin.openai_codex",
                display_name="OpenAI Codex",
                version="0.1.0",
                family="openai-codex",
                entrypoint="<builtin>",
                supported_auth_modes=[
                    "oauth_browser",
                    "codex_auth_file",
                    "api_key",
                    "stored_token",
                ],
                default_auth_mode="oauth_browser",
                capabilities=[
                    "list_models",
                    "chat",
                    "oauth_pkce_login",
                    "api_key_auth",
                    "stored_token_auth",
                    "codex_auth_file_auth",
                ],
                required_config=[],
                optional_config=[
                    "auth",
                    "api_key_secret",
                    "base_url",
                    "model",
                    "models_path",
                    "chat_path",
                    "redirect_uri",
                    "timeout_seconds",
                    "auth_file",
                ],
                secret_config=["api_key_secret"],
                credential_fields=[
                    "api_key",
                    "access_token",
                    "refresh_token",
                    "expires_at",
                    "scope",
                    "subject",
                    "id_token",
                    "auth_file",
                ],
            ),
            default_base_url="https://api.openai.com/v1",
            default_secret_name="CODEX_API_KEY",
            default_auth_file="~/.codex/auth.json",
        ),
        AnthropicProviderPlugin(
            manifest=ProviderPluginManifest(
                plugin_id="builtin.anthropic",
                display_name="Anthropic API",
                version="0.1.0",
                family="anthropic",
                entrypoint="<builtin>",
                supported_auth_modes=["api_key", "stored_token"],
                default_auth_mode="api_key",
                capabilities=["list_models", "chat", "api_key_auth", "stored_token_auth"],
                required_config=[],
                optional_config=[
                    "auth",
                    "api_key_secret",
                    "base_url",
                    "model",
                    "models_path",
                    "chat_path",
                    "api_version",
                    "max_tokens",
                    "timeout_seconds",
                ],
                secret_config=["api_key_secret"],
                credential_fields=["access_token", "refresh_token", "expires_at"],
            ),
            default_base_url="https://api.anthropic.com/v1",
            default_secret_name="ANTHROPIC_API_KEY",
            auth_header_name="x-api-key",
            auth_header_format="{token}",
        ),
        GeminiProviderPlugin(
            manifest=ProviderPluginManifest(
                plugin_id="builtin.gemini",
                display_name="Google Gemini API",
                version="0.1.0",
                family="gemini",
                entrypoint="<builtin>",
                supported_auth_modes=["api_key"],
                default_auth_mode="api_key",
                capabilities=["list_models", "chat", "api_key_auth"],
                required_config=[],
                optional_config=[
                    "auth",
                    "api_key_secret",
                    "base_url",
                    "model",
                    "models_path",
                    "timeout_seconds",
                ],
                secret_config=["api_key_secret"],
            ),
            default_base_url="https://generativelanguage.googleapis.com/v1beta",
            default_secret_name="GEMINI_API_KEY",
            query_auth_parameter="key",
        ),
        HttpProviderPlugin(
            manifest=ProviderPluginManifest(
                plugin_id="builtin.deepseek",
                display_name="DeepSeek API",
                version="0.1.0",
                family="deepseek",
                entrypoint="<builtin>",
                supported_auth_modes=["api_key", "stored_token"],
                default_auth_mode="api_key",
                capabilities=["list_models", "chat", "api_key_auth", "stored_token_auth"],
                required_config=[],
                optional_config=[
                    "auth",
                    "api_key_secret",
                    "base_url",
                    "model",
                    "models_path",
                    "chat_path",
                    "timeout_seconds",
                ],
                secret_config=["api_key_secret"],
                credential_fields=["access_token", "refresh_token", "expires_at"],
            ),
            default_base_url="https://api.deepseek.com",
            default_secret_name="DEEPSEEK_API_KEY",
        ),
        HttpProviderPlugin(
            manifest=ProviderPluginManifest(
                plugin_id="builtin.openai_compatible",
                display_name="OpenAI-Compatible API",
                version="0.1.0",
                family="openai-compatible",
                entrypoint="<builtin>",
                supported_auth_modes=["api_key", "stored_token"],
                default_auth_mode="api_key",
                capabilities=["list_models", "chat", "api_key_auth", "stored_token_auth"],
                required_config=["base_url"],
                optional_config=[
                    "auth",
                    "api_key_secret",
                    "model",
                    "models_path",
                    "chat_path",
                    "timeout_seconds",
                ],
                secret_config=["api_key_secret"],
                credential_fields=["access_token", "refresh_token", "expires_at"],
            ),
            default_base_url="https://example.invalid/v1",
            default_secret_name="OPENAI_COMPATIBLE_API_KEY",
        ),
        AnthropicProviderPlugin(
            manifest=ProviderPluginManifest(
                plugin_id="builtin.anthropic_compatible",
                display_name="Anthropic-Compatible API",
                version="0.1.0",
                family="anthropic-compatible",
                entrypoint="<builtin>",
                supported_auth_modes=["api_key", "stored_token"],
                default_auth_mode="api_key",
                capabilities=["list_models", "chat", "api_key_auth", "stored_token_auth"],
                required_config=["base_url"],
                optional_config=[
                    "auth",
                    "api_key_secret",
                    "model",
                    "models_path",
                    "chat_path",
                    "api_version",
                    "max_tokens",
                    "timeout_seconds",
                ],
                secret_config=["api_key_secret"],
                credential_fields=["access_token", "refresh_token", "expires_at"],
            ),
            default_base_url="https://example.invalid/v1",
            default_secret_name="ANTHROPIC_COMPATIBLE_API_KEY",
            auth_header_name="x-api-key",
            auth_header_format="{token}",
        ),
        OllamaProviderPlugin(
            manifest=ProviderPluginManifest(
                plugin_id="builtin.ollama",
                display_name="Ollama",
                version="0.1.0",
                family="ollama",
                entrypoint="<builtin>",
                supported_auth_modes=["none", "api_key", "stored_token"],
                default_auth_mode="none",
                capabilities=["list_models", "chat", "local_http", "api_key_auth", "no_auth"],
                required_config=[],
                optional_config=[
                    "auth",
                    "api_key_secret",
                    "base_url",
                    "model",
                    "models_path",
                    "chat_path",
                    "timeout_seconds",
                ],
                secret_config=["api_key_secret"],
                credential_fields=["access_token", "refresh_token", "expires_at"],
            ),
            default_base_url="http://127.0.0.1:11434",
            default_secret_name="OLLAMA_API_KEY",
            list_models_path="/api/tags",
        ),
        HttpProviderPlugin(
            manifest=ProviderPluginManifest(
                plugin_id="builtin.azure_openai",
                display_name="Azure OpenAI",
                version="0.1.0",
                family="azure-openai",
                entrypoint="<builtin>",
                supported_auth_modes=["api_key", "stored_token"],
                default_auth_mode="api_key",
                capabilities=["api_key_auth", "stored_token_auth", "deployment_target"],
                required_config=["base_url", "api_version", "deployment"],
                optional_config=[
                    "auth",
                    "api_key_secret",
                    "model",
                    "timeout_seconds",
                ],
                secret_config=["api_key_secret"],
                credential_fields=["access_token", "refresh_token", "expires_at"],
            ),
            default_base_url="https://example.openai.azure.com/openai",
            default_secret_name="AZURE_OPENAI_API_KEY",
            auth_header_name="api-key",
            auth_header_format="{token}",
        ),
        CredentialFileProviderPlugin(
            manifest=ProviderPluginManifest(
                plugin_id="builtin.vertex_ai",
                display_name="Google Vertex AI",
                version="0.1.0",
                family="vertex-ai",
                entrypoint="<builtin>",
                supported_auth_modes=["credential_file", "stored_token"],
                default_auth_mode="credential_file",
                capabilities=["credential_file_auth", "enterprise"],
                required_config=["project_id", "location"],
                optional_config=["auth", "credential_file", "model"],
                credential_fields=["access_token", "refresh_token", "expires_at"],
            ),
            credential_label="Vertex AI",
        ),
        CredentialFileProviderPlugin(
            manifest=ProviderPluginManifest(
                plugin_id="builtin.bedrock",
                display_name="Amazon Bedrock",
                version="0.1.0",
                family="bedrock",
                entrypoint="<builtin>",
                supported_auth_modes=["credential_file", "stored_token"],
                default_auth_mode="credential_file",
                capabilities=["credential_file_auth", "enterprise"],
                required_config=["region"],
                optional_config=["auth", "credential_file", "profile_name", "model"],
                credential_fields=["access_token", "refresh_token", "expires_at"],
            ),
            credential_label="Bedrock",
        ),
    ]
    return [
        LoadedProviderPlugin(
            manifest=provider.manifest,
            implementation=provider,
            source="<builtin>",
        )
        for provider in providers
    ]


def _auth_mode(config: Mapping[str, object], default_auth_mode: str) -> str:
    auth_mode = config.get("auth", default_auth_mode)
    if not isinstance(auth_mode, str) or not auth_mode.strip():
        return default_auth_mode
    return auth_mode.strip()


def _string_config(config: Mapping[str, object], key: str) -> str | None:
    value = config.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _token_from_credential(credential: CredentialRecord | None) -> str:
    if credential is None:
        return ""
    for field_name in ("access_token", "token", "api_key"):
        value = credential.data.get(field_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _credential_field(credential: CredentialRecord | None, field_name: str) -> str:
    if credential is None:
        return ""
    value = credential.data.get(field_name)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def _first_present_env(variable_names: tuple[str, ...]) -> tuple[str | None, str | None]:
    for variable_name in variable_names:
        value = os.environ.get(variable_name, "")
        if value.strip():
            return variable_name, value.strip()
    return None, None


def _load_codex_auth_cache(auth_file: Path) -> _CodexAuthCache:
    if not auth_file.exists():
        return _CodexAuthCache(path=auth_file)

    try:
        payload = json.loads(auth_file.read_text(encoding="utf-8"))
    except OSError as exc:
        return _CodexAuthCache(path=auth_file, error=str(exc))
    except ValueError as exc:
        return _CodexAuthCache(path=auth_file, error=f"invalid JSON: {exc}")

    if not isinstance(payload, dict):
        return _CodexAuthCache(path=auth_file, error="auth cache payload must be a JSON object")

    tokens = payload.get("tokens")
    token_payload = tokens if isinstance(tokens, dict) else {}

    return _CodexAuthCache(
        path=auth_file,
        api_key=_as_string(payload.get("OPENAI_API_KEY")),
        access_token=_as_string(token_payload.get("access_token")),
        refresh_token=_as_string(token_payload.get("refresh_token")),
    )


def _as_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _pkce_verifier() -> str:
    return secretslib.token_urlsafe(64)


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def _parse_oauth_callback(callback_url: str) -> dict[str, str]:
    if not callback_url.strip():
        return {}
    if "://" not in callback_url:
        return {"code": callback_url.strip()}
    query = parse_qs(urlsplit(callback_url).query)
    return {
        key: values[0].strip()
        for key, values in query.items()
        if values and values[0].strip()
    }


def _expiry_timestamp(expires_in: object) -> str | None:
    if not isinstance(expires_in, int) or expires_in <= 0:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + expires_in))


def _is_expired(expires_at: str) -> bool:
    if not expires_at:
        return False
    try:
        expires_struct = time.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return time.time() >= calendar.timegm(expires_struct)


def _jwt_subject(token: str) -> str | None:
    parts = token.split(".")
    if len(parts) < 2:
        return None
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8")
        payload_json = json.loads(decoded)
    except (ValueError, OSError):
        return None
    if not isinstance(payload_json, dict):
        return None
    subject = payload_json.get("sub")
    if isinstance(subject, str) and subject.strip():
        return subject.strip()
    return None


def _parse_data_models(payload: object, provider_id: str) -> list[ProviderModel]:
    if not isinstance(payload, dict):
        raise ProviderHttpError(
            f"Provider {provider_id!r} returned an unexpected model response."
        )
    raw_models = payload.get("data", [])
    if not isinstance(raw_models, list):
        raise ProviderHttpError(
            f"Provider {provider_id!r} returned an invalid model listing payload."
        )
    models: list[ProviderModel] = []
    for item in raw_models:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id", "")).strip()
        if not model_id:
            continue
        display_name = str(item.get("display_name", item.get("name", model_id)))
        models.append(
            ProviderModel(
                model_id=model_id,
                display_name=display_name,
                metadata=dict(item),
            )
        )
    return models


def _require_model(provider_id: str, config: Mapping[str, object]) -> str:
    model = _string_config(config, "model")
    if model is None:
        raise ValueError(f"Provider {provider_id!r} does not define a model yet.")
    return model


def _parse_openai_chat_message(payload: object, provider_id: str) -> str:
    if not isinstance(payload, dict):
        raise ProviderHttpError(
            f"Provider {provider_id!r} returned an unexpected chat response."
        )
    choices = payload.get("choices", [])
    if not isinstance(choices, list) or not choices:
        raise ProviderHttpError(
            f"Provider {provider_id!r} returned no chat choices."
        )
    first = choices[0]
    if not isinstance(first, dict):
        raise ProviderHttpError(
            f"Provider {provider_id!r} returned an invalid chat choice."
        )
    message = first.get("message", {})
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            text_parts = [
                str(part.get("text", "")).strip()
                for part in content
                if isinstance(part, dict) and str(part.get("text", "")).strip()
            ]
            if text_parts:
                return "\n".join(text_parts)
    raise ProviderHttpError(
        f"Provider {provider_id!r} returned a chat response without text."
    )


def _parse_anthropic_message(payload: object, provider_id: str) -> str:
    if not isinstance(payload, dict):
        raise ProviderHttpError(
            f"Provider {provider_id!r} returned an unexpected Anthropic response."
        )
    content = payload.get("content", [])
    if not isinstance(content, list):
        raise ProviderHttpError(
            f"Provider {provider_id!r} returned an invalid Anthropic content payload."
        )
    text_parts = [
        str(item.get("text", "")).strip()
        for item in content
        if isinstance(item, dict) and str(item.get("text", "")).strip()
    ]
    if text_parts:
        return "\n".join(text_parts)
    raise ProviderHttpError(
        f"Provider {provider_id!r} returned an Anthropic response without text."
    )


def _parse_gemini_message(payload: object, provider_id: str) -> str:
    if not isinstance(payload, dict):
        raise ProviderHttpError(
            f"Provider {provider_id!r} returned an unexpected Gemini response."
        )
    candidates = payload.get("candidates", [])
    if not isinstance(candidates, list) or not candidates:
        raise ProviderHttpError(
            f"Provider {provider_id!r} returned no Gemini candidates."
        )
    first = candidates[0]
    if not isinstance(first, dict):
        raise ProviderHttpError(
            f"Provider {provider_id!r} returned an invalid Gemini candidate."
        )
    content = first.get("content", {})
    if not isinstance(content, dict):
        raise ProviderHttpError(
            f"Provider {provider_id!r} returned Gemini content in an invalid shape."
        )
    parts = content.get("parts", [])
    if not isinstance(parts, list):
        raise ProviderHttpError(
            f"Provider {provider_id!r} returned invalid Gemini parts."
        )
    text_parts = [
        str(item.get("text", "")).strip()
        for item in parts
        if isinstance(item, dict) and str(item.get("text", "")).strip()
    ]
    if text_parts:
        return "\n".join(text_parts)
    raise ProviderHttpError(
        f"Provider {provider_id!r} returned a Gemini response without text."
    )


def _parse_ollama_message(payload: object, provider_id: str) -> str:
    if not isinstance(payload, dict):
        raise ProviderHttpError(
            f"Provider {provider_id!r} returned an unexpected Ollama response."
        )
    message = payload.get("message", {})
    if not isinstance(message, dict):
        raise ProviderHttpError(
            f"Provider {provider_id!r} returned an invalid Ollama message payload."
        )
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    raise ProviderHttpError(
        f"Provider {provider_id!r} returned an Ollama response without text."
    )


def _timeout_seconds(config: Mapping[str, object]) -> float:
    value = config.get("timeout_seconds", 15)
    if isinstance(value, bool):
        return 15.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 15.0
    return 15.0


def _issue(
    severity: str,
    code: str,
    source: str,
    message: str,
    *,
    hint: str | None = None,
) -> CheckIssue:
    return CheckIssue(
        severity=severity,
        code=code,
        message=message,
        source=source,
        hint=hint,
    )
