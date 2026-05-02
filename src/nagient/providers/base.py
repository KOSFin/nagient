from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from nagient.domain.entities.agent_runtime import AssistantResponse
from nagient.domain.entities.config_fields import ConfigFieldSpec
from nagient.domain.entities.system_state import (
    AuthSessionState,
    CheckIssue,
    CredentialRecord,
    ProviderAuthStatus,
    ProviderModel,
)

REQUIRED_PROVIDER_METHODS = (
    "validate_config",
    "self_test",
    "healthcheck",
    "auth_status",
    "begin_login",
    "complete_login",
    "logout",
    "list_models",
)


@dataclass(frozen=True)
class ProviderPluginManifest:
    plugin_id: str
    display_name: str
    version: str
    family: str
    entrypoint: str
    supported_auth_modes: list[str]
    default_auth_mode: str
    capabilities: list[str] = field(default_factory=list)
    required_config: list[str] = field(default_factory=list)
    optional_config: list[str] = field(default_factory=list)
    secret_config: list[str] = field(default_factory=list)
    credential_fields: list[str] = field(default_factory=list)
    config_fields: list[ConfigFieldSpec] = field(default_factory=list)
    config_schema_file: str | None = None

    @property
    def allowed_config(self) -> set[str]:
        return set(self.required_config) | set(self.optional_config)

    def field_by_key(self, key: str) -> ConfigFieldSpec | None:
        for field_spec in self.config_fields:
            if field_spec.key == key:
                return field_spec
        return None


@dataclass(frozen=True)
class LoadedProviderPlugin:
    manifest: ProviderPluginManifest
    implementation: BaseProviderPlugin
    source: str


@dataclass(frozen=True)
class ProviderRuntimeContext:
    state_dir: Path
    log: Callable[[str], None]


class BaseProviderPlugin:
    manifest: ProviderPluginManifest

    def bind_runtime(
        self,
        provider_id: str,
        runtime: ProviderRuntimeContext,
    ) -> None:
        object.__setattr__(self, "_runtime_provider_id", provider_id)
        object.__setattr__(self, "_runtime_context", runtime)

    @property
    def runtime(self) -> ProviderRuntimeContext | None:
        runtime = getattr(self, "_runtime_context", None)
        if isinstance(runtime, ProviderRuntimeContext):
            return runtime
        return None

    def runtime_log(self, message: str) -> None:
        runtime = self.runtime
        if runtime is not None:
            runtime.log(message)

    def validate_config(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> list[CheckIssue]:
        del provider_id, config, secrets, credential
        return []

    def self_test(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> list[CheckIssue]:
        del provider_id, config, secrets, credential
        return []

    def healthcheck(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> list[CheckIssue]:
        del provider_id, config, secrets, credential
        return []

    def auth_status(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> ProviderAuthStatus:
        del provider_id, config, secrets, credential
        return ProviderAuthStatus(
            authenticated=False,
            auth_mode="unsupported",
            status="unsupported",
            message="The provider does not implement auth_status().",
        )

    def begin_login(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> AuthSessionState:
        del provider_id, config, secrets, credential
        raise NotImplementedError

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

    def logout(
        self,
        provider_id: str,
        config: Mapping[str, object],
        credential: CredentialRecord | None,
    ) -> None:
        del provider_id, config, credential
        return None

    def list_models(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> list[ProviderModel]:
        del provider_id, config, secrets, credential
        return []

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
        del provider_id, config, secrets, credential, message, system_prompt
        raise NotImplementedError

    def generate_assistant_response(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
        *,
        message: str,
        system_prompt: str,
        session_id: str,
        transport_id: str,
        prompt_context: object,
        tool_catalog: list[dict[str, object]],
        transport_catalog: list[dict[str, object]],
        previous_results: list[dict[str, object]],
    ) -> AssistantResponse:
        del (
            provider_id,
            config,
            secrets,
            credential,
            message,
            system_prompt,
            session_id,
            transport_id,
            prompt_context,
            tool_catalog,
            transport_catalog,
            previous_results,
        )
        raise NotImplementedError
