from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from nagient.domain.entities.system_state import (
    AuthSessionState,
    CheckIssue,
    CredentialRecord,
    ProviderAuthStatus,
    ProviderModel,
)
from nagient.providers.base import BaseProviderPlugin, LoadedProviderPlugin, ProviderPluginManifest
from nagient.providers.http import JsonHttpClient, ProviderHttpError


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

    def _secret_name(self, config: Mapping[str, object]) -> str | None:
        secret_name = _string_config(config, "api_key_secret")
        if secret_name is not None:
            return secret_name
        return self.default_secret_name

    def _models_url(self, config: Mapping[str, object]) -> str:
        base_url = _string_config(config, "base_url") or self.default_base_url
        models_path = _string_config(config, "models_path") or self.list_models_path
        return f"{base_url.rstrip('/')}{models_path}"

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
                capabilities=["list_models", "api_key_auth", "stored_token_auth"],
                required_config=[],
                optional_config=[
                    "auth",
                    "api_key_secret",
                    "base_url",
                    "model",
                    "models_path",
                    "organization",
                    "timeout_seconds",
                ],
                secret_config=["api_key_secret"],
                credential_fields=["access_token", "refresh_token", "expires_at"],
            ),
            default_base_url="https://api.openai.com/v1",
            default_secret_name="OPENAI_API_KEY",
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
                capabilities=["list_models", "api_key_auth", "stored_token_auth"],
                required_config=[],
                optional_config=[
                    "auth",
                    "api_key_secret",
                    "base_url",
                    "model",
                    "models_path",
                    "api_version",
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
                capabilities=["list_models", "api_key_auth"],
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
                capabilities=["list_models", "api_key_auth", "stored_token_auth"],
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
                capabilities=["list_models", "api_key_auth", "stored_token_auth"],
                required_config=["base_url"],
                optional_config=[
                    "auth",
                    "api_key_secret",
                    "model",
                    "models_path",
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
                capabilities=["list_models", "api_key_auth", "stored_token_auth"],
                required_config=["base_url"],
                optional_config=[
                    "auth",
                    "api_key_secret",
                    "model",
                    "models_path",
                    "api_version",
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
                capabilities=["list_models", "local_http", "api_key_auth", "no_auth"],
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
