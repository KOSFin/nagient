from __future__ import annotations

import getpass
import json
import time
from dataclasses import dataclass

from nagient.app.configuration import (
    ProviderInstanceConfig,
    RuntimeConfiguration,
    load_runtime_configuration,
)
from nagient.app.settings import Settings
from nagient.domain.entities.agent_runtime import AssistantResponse
from nagient.domain.entities.system_state import CredentialRecord, ProviderState
from nagient.infrastructure.logging import RuntimeLogger
from nagient.providers.base import LoadedProviderPlugin
from nagient.providers.manager import ProviderManager
from nagient.providers.registry import ProviderPluginRegistry
from nagient.providers.storage import AuthSessionStore, FileCredentialStore
from nagient.security.broker import SecretBroker


@dataclass(frozen=True)
class ProviderService:
    settings: Settings
    provider_registry: ProviderPluginRegistry
    provider_manager: ProviderManager
    credential_store: FileCredentialStore
    auth_session_store: AuthSessionStore
    secret_broker: SecretBroker | None = None
    logger: RuntimeLogger | None = None

    def auth_status(
        self,
        provider_id: str | None = None,
        *,
        verify_remote: bool = False,
    ) -> dict[str, object]:
        runtime_config = load_runtime_configuration(self.settings)
        discovery = self.provider_registry.discover(self.settings.providers_dir)
        if provider_id is None:
            providers = [
                self._inspect_provider(
                    runtime_config,
                    discovery.plugins[provider.plugin_id],
                    provider.provider_id,
                    verify_remote=verify_remote,
                )
                for provider in runtime_config.providers
                if provider.plugin_id in discovery.plugins
            ]
            return {
                "providers": [provider.to_dict() for provider in providers],
                "issues": [issue.to_dict() for issue in discovery.issues],
            }

        provider_config, plugin = self._resolve_provider(
            runtime_config,
            discovery.plugins,
            provider_id,
        )
        state = self._inspect_provider(
            runtime_config,
            plugin,
            provider_config.provider_id,
            verify_remote=verify_remote,
        )
        return {
            "provider": state.to_dict(),
            "issues": [issue.to_dict() for issue in discovery.issues],
        }

    def list_models(self, provider_id: str) -> dict[str, object]:
        runtime_config = load_runtime_configuration(self.settings)
        discovery = self.provider_registry.discover(self.settings.providers_dir)
        provider_config, plugin = self._resolve_provider(
            runtime_config,
            discovery.plugins,
            provider_id,
        )
        if "list_models" not in plugin.manifest.capabilities:
            raise ValueError(
                f"Provider plugin {plugin.manifest.plugin_id!r} does not support "
                "model discovery."
            )
        credential = self.credential_store.load(provider_config.provider_id)
        credential = self._refresh_credential_if_needed(
            plugin,
            provider_config.provider_id,
            provider_config.config,
            credential,
        )
        models = plugin.implementation.list_models(
            provider_config.provider_id,
            provider_config.config,
            runtime_config.secrets,
            credential,
        )
        self._log(
            "info",
            "provider.list_models",
            "Listed provider models.",
            provider_id=provider_config.provider_id,
            plugin_id=provider_config.plugin_id,
            models=len(models),
        )
        return {
            "provider_id": provider_config.provider_id,
            "plugin_id": provider_config.plugin_id,
            "models": [model.to_dict() for model in models],
        }

    def chat(
        self,
        *,
        message: str,
        provider_id: str | None = None,
        system_prompt: str | None = None,
    ) -> dict[str, object]:
        runtime_config = load_runtime_configuration(self.settings)
        discovery = self.provider_registry.discover(self.settings.providers_dir)
        resolved_provider_id = provider_id or runtime_config.default_provider
        if not resolved_provider_id:
            raise ValueError(
                "No provider was selected. Configure [agent].default_provider or pass --provider."
            )
        provider_config, plugin = self._resolve_provider(
            runtime_config,
            discovery.plugins,
            resolved_provider_id,
        )
        generate_message = getattr(plugin.implementation, "generate_message", None)
        if not callable(generate_message):
            raise ValueError(
                f"Provider {resolved_provider_id!r} does not support CLI chat."
            )
        credential = self.credential_store.load(provider_config.provider_id)
        credential = self._refresh_credential_if_needed(
            plugin,
            provider_config.provider_id,
            provider_config.config,
            credential,
        )
        response_text = generate_message(
            provider_config.provider_id,
            provider_config.config,
            runtime_config.secrets,
            credential,
            message=message,
            system_prompt=system_prompt,
        )
        self._log(
            "info",
            "provider.chat",
            "Generated chat response through provider.",
            provider_id=provider_config.provider_id,
            plugin_id=provider_config.plugin_id,
            transport_id="console",
        )
        return {
            "provider_id": provider_config.provider_id,
            "plugin_id": provider_config.plugin_id,
            "model": provider_config.config.get("model"),
            "transport_id": "console",
            "message": response_text,
        }

    def generate_assistant_response(
        self,
        *,
        message: str,
        provider_id: str | None = None,
        session_id: str,
        transport_id: str,
        system_prompt: str,
        prompt_context: object,
        tool_catalog: list[dict[str, object]],
        transport_catalog: list[dict[str, object]],
        previous_results: list[dict[str, object]],
    ) -> AssistantResponse:
        runtime_config = load_runtime_configuration(self.settings)
        discovery = self.provider_registry.discover(self.settings.providers_dir)
        resolved_provider_id = provider_id or runtime_config.default_provider
        if not resolved_provider_id:
            raise ValueError(
                "No provider was selected. Configure [agent].default_provider or pass --provider."
            )
        provider_config, plugin = self._resolve_provider(
            runtime_config,
            discovery.plugins,
            resolved_provider_id,
        )
        credential = self.credential_store.load(provider_config.provider_id)
        credential = self._refresh_credential_if_needed(
            plugin,
            provider_config.provider_id,
            provider_config.config,
            credential,
        )
        generate_structured = getattr(
            plugin.implementation,
            "generate_assistant_response",
            None,
        )
        if callable(generate_structured):
            response = generate_structured(
                provider_config.provider_id,
                provider_config.config,
                runtime_config.secrets,
                credential,
                message=message,
                system_prompt=system_prompt,
                session_id=session_id,
                transport_id=transport_id,
                prompt_context=prompt_context,
                tool_catalog=tool_catalog,
                transport_catalog=transport_catalog,
                previous_results=previous_results,
            )
            if not isinstance(response, AssistantResponse):
                raise ValueError("Structured provider response must return AssistantResponse.")
            self._log(
                "info",
                "provider.generate_assistant_response",
                "Generated structured assistant response through native provider path.",
                provider_id=provider_config.provider_id,
                plugin_id=provider_config.plugin_id,
                session_id=session_id,
                transport_id=transport_id,
                tool_calls=len(response.tool_calls),
            )
            return response

        generate_message = getattr(plugin.implementation, "generate_message", None)
        if not callable(generate_message):
            raise ValueError(
                f"Provider {resolved_provider_id!r} does not support agent runtime turns."
            )
        response_text = generate_message(
            provider_config.provider_id,
            provider_config.config,
            runtime_config.secrets,
            credential,
            message=_build_structured_assistant_prompt(
                session_id=session_id,
                transport_id=transport_id,
                user_message=message,
                prompt_context=prompt_context,
                tool_catalog=tool_catalog,
                transport_catalog=transport_catalog,
                previous_results=previous_results,
            ),
            system_prompt=system_prompt,
        )
        parsed = _parse_assistant_response(response_text)
        self._log(
            "info",
            "provider.generate_assistant_response",
            "Generated structured assistant response through JSON fallback path.",
            provider_id=provider_config.provider_id,
            plugin_id=provider_config.plugin_id,
            session_id=session_id,
            transport_id=transport_id,
            tool_calls=len(parsed.tool_calls),
        )
        return parsed

    def login(
        self,
        provider_id: str,
        *,
        api_key: str | None = None,
        token: str | None = None,
        secret_name: str | None = None,
    ) -> dict[str, object]:
        runtime_config = load_runtime_configuration(self.settings)
        discovery = self.provider_registry.discover(self.settings.providers_dir)
        provider_config, plugin = self._resolve_provider(
            runtime_config,
            discovery.plugins,
            provider_id,
        )
        auth_mode = _auth_mode(provider_config.config, plugin.manifest.default_auth_mode)

        if auth_mode == "none":
            state = self._inspect_provider(runtime_config, plugin, provider_id)
            return {
                "provider": state.to_dict(),
                "message": "This provider profile does not require credentials.",
            }

        if auth_mode == "api_key":
            resolved_api_key = api_key
            if resolved_api_key is None and _stdin_is_tty():
                resolved_api_key = getpass.getpass(
                    prompt=f"Enter API key for provider {provider_id}: "
                ).strip()
            if not resolved_api_key:
                resolved_secret_name = self._secret_name(
                    provider_config.config,
                    plugin,
                    secret_name,
                )
                return {
                    "provider_id": provider_id,
                    "auth_mode": auth_mode,
                    "status": "awaiting_secret",
                    "secret_name": resolved_secret_name,
                    "message": (
                        "No API key was provided. Pass --api-key, use an interactive TTY, "
                        "or add the key to secrets.env manually."
                    ),
                }
            resolved_secret_name = self._secret_name(
                provider_config.config,
                plugin,
                secret_name,
            )
            if resolved_secret_name is None:
                raise ValueError(
                    f"Provider {provider_id!r} does not define api_key_secret and has no "
                    "built-in default secret name."
                )
            secret_broker = self._secret_broker()
            secret_broker.store_secret(
                resolved_secret_name,
                resolved_api_key,
                scope="core",
            )
            secret_broker.bind_secret(
                resolved_secret_name,
                target_kind="provider",
                target_id=provider_id,
                scope_hint="core",
            )
            reloaded_runtime_config = load_runtime_configuration(self.settings)
            state = self._inspect_provider(reloaded_runtime_config, plugin, provider_id)
            self._log(
                "info",
                "provider.login",
                "Stored API key secret for provider.",
                provider_id=provider_id,
                plugin_id=plugin.manifest.plugin_id,
                auth_mode=auth_mode,
                secret_name=resolved_secret_name,
            )
            return {
                "provider": state.to_dict(),
                "auth_mode": auth_mode,
                "secret_name": resolved_secret_name,
                "secrets_file": str(self.settings.secrets_file),
            }

        if auth_mode == "stored_token":
            if token:
                record = CredentialRecord(
                    provider_id=provider_id,
                    plugin_id=plugin.manifest.plugin_id,
                    auth_mode="stored_token",
                    issued_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    data={"access_token": token},
                )
                path = self.credential_store.save(provider_id, record)
                state = self._inspect_provider(runtime_config, plugin, provider_id)
                self._log(
                    "info",
                    "provider.login",
                    "Stored provider token credential.",
                    provider_id=provider_id,
                    plugin_id=plugin.manifest.plugin_id,
                    auth_mode=auth_mode,
                )
                return {
                    "provider": state.to_dict(),
                    "credential_path": str(path),
                }

            credential = self.credential_store.load(provider_id)
            session = plugin.implementation.begin_login(
                provider_id,
                provider_config.config,
                runtime_config.secrets,
                credential,
            )
            session_path = self.auth_session_store.save(session)
            return {
                "provider_id": provider_id,
                "plugin_id": plugin.manifest.plugin_id,
                "session": session.to_dict(),
                "session_path": str(session_path),
            }

        credential = self.credential_store.load(provider_id)
        session = plugin.implementation.begin_login(
            provider_id,
            provider_config.config,
            runtime_config.secrets,
            credential,
        )
        session_path = self.auth_session_store.save(session)
        self._log(
            "info",
            "provider.login",
            "Created provider auth session.",
            provider_id=provider_id,
            plugin_id=plugin.manifest.plugin_id,
            auth_mode=auth_mode,
        )
        return {
            "provider_id": provider_id,
            "plugin_id": plugin.manifest.plugin_id,
            "session": session.to_dict(),
            "session_path": str(session_path),
        }

    def complete_login(
        self,
        provider_id: str,
        session_id: str,
        *,
        callback_url: str | None = None,
        code: str | None = None,
    ) -> dict[str, object]:
        runtime_config = load_runtime_configuration(self.settings)
        discovery = self.provider_registry.discover(self.settings.providers_dir)
        provider_config, plugin = self._resolve_provider(
            runtime_config,
            discovery.plugins,
            provider_id,
        )
        session = self.auth_session_store.load(session_id)
        if session is None:
            raise ValueError(f"Auth session {session_id!r} was not found.")
        if session.provider_id != provider_id:
            raise ValueError(
                f"Auth session {session_id!r} belongs to provider {session.provider_id!r}, not "
                f"{provider_id!r}."
            )

        credential = self.credential_store.load(provider_id)
        record = plugin.implementation.complete_login(
            provider_id,
            provider_config.config,
            credential,
            session,
            callback_url=callback_url,
            code=code,
        )
        path = self.credential_store.save(provider_id, record)
        self.auth_session_store.delete(session_id)
        state = self._inspect_provider(runtime_config, plugin, provider_id)
        self._log(
            "info",
            "provider.complete_login",
            "Completed provider login flow.",
            provider_id=provider_id,
            plugin_id=plugin.manifest.plugin_id,
            session_id=session_id,
        )
        return {
            "provider": state.to_dict(),
            "credential_path": str(path),
        }

    def logout(self, provider_id: str) -> dict[str, object]:
        runtime_config = load_runtime_configuration(self.settings)
        discovery = self.provider_registry.discover(self.settings.providers_dir)
        provider_config, plugin = self._resolve_provider(
            runtime_config,
            discovery.plugins,
            provider_id,
        )
        auth_mode = _auth_mode(provider_config.config, plugin.manifest.default_auth_mode)
        credential = self.credential_store.load(provider_id)
        plugin.implementation.logout(provider_id, provider_config.config, credential)
        deleted = self.credential_store.delete(provider_id)
        deleted_secret = False
        if auth_mode == "api_key":
            secret_name = self._secret_name(provider_config.config, plugin, None)
            if secret_name is not None:
                deleted_secret = self._secret_broker().remove_secret(
                    secret_name,
                    scope_hint="core",
                )
        reloaded_runtime_config = load_runtime_configuration(self.settings)
        state = self._inspect_provider(reloaded_runtime_config, plugin, provider_id)
        self._log(
            "info",
            "provider.logout",
            "Cleared provider credentials.",
            provider_id=provider_id,
            plugin_id=plugin.manifest.plugin_id,
            deleted=deleted or deleted_secret,
        )
        return {
            "provider": state.to_dict(),
            "deleted": deleted or deleted_secret,
            "deleted_secret": deleted_secret,
        }

    def _inspect_provider(
        self,
        runtime_config: RuntimeConfiguration,
        plugin: LoadedProviderPlugin,
        provider_id: str,
        *,
        verify_remote: bool = False,
    ) -> ProviderState:
        provider_config = next(
            provider
            for provider in runtime_config.providers
            if provider.provider_id == provider_id
        )
        credential = self.credential_store.load(provider_config.provider_id)
        return self.provider_manager.inspect_provider(
            provider_config,
            plugin,
            runtime_config.secrets,
            credential,
            is_default=runtime_config.default_provider == provider_config.provider_id,
            verify_remote=verify_remote,
        )

    def _resolve_provider(
        self,
        runtime_config: RuntimeConfiguration,
        plugins: dict[str, LoadedProviderPlugin],
        provider_id: str,
    ) -> tuple[ProviderInstanceConfig, LoadedProviderPlugin]:
        provider_config = next(
            (
                provider
                for provider in runtime_config.providers
                if provider.provider_id == provider_id
            ),
            None,
        )
        if provider_config is None:
            raise ValueError(f"Provider profile {provider_id!r} is not defined in config.toml.")
        plugin = plugins.get(provider_config.plugin_id)
        if plugin is None:
            raise ValueError(
                f"Provider profile {provider_id!r} references unknown plugin "
                f"{provider_config.plugin_id!r}."
            )
        return provider_config, plugin

    def _secret_name(
        self,
        config: dict[str, object],
        plugin: LoadedProviderPlugin,
        override: str | None,
    ) -> str | None:
        if override:
            return override
        secret_name = config.get("api_key_secret")
        if isinstance(secret_name, str) and secret_name.strip():
            return secret_name.strip()
        default_secret_name = getattr(plugin.implementation, "default_secret_name", None)
        if isinstance(default_secret_name, str) and default_secret_name.strip():
            return default_secret_name.strip()
        return None

    def _secret_broker(self) -> SecretBroker:
        return self.secret_broker or SecretBroker(self.settings)

    def _refresh_credential_if_needed(
        self,
        plugin: LoadedProviderPlugin,
        provider_id: str,
        config: dict[str, object],
        credential: CredentialRecord | None,
    ) -> CredentialRecord | None:
        refresh_credential = getattr(plugin.implementation, "refresh_credential", None)
        if not callable(refresh_credential):
            return credential
        refreshed = refresh_credential(provider_id, config, credential)
        if not isinstance(refreshed, CredentialRecord):
            return credential
        self.credential_store.save(provider_id, refreshed)
        return refreshed

    def _log(
        self,
        level: str,
        event: str,
        message: str,
        **fields: object,
    ) -> None:
        if self.logger is None:
            return
        log_method = getattr(self.logger, level, None)
        if callable(log_method):
            log_method(event, message, **fields)


def _auth_mode(config: dict[str, object], default_auth_mode: str) -> str:
    value = config.get("auth")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default_auth_mode


def _stdin_is_tty() -> bool:
    try:
        import sys

        return sys.stdin.isatty()
    except Exception:
        return False


def _build_structured_assistant_prompt(
    *,
    session_id: str,
    transport_id: str,
    user_message: str,
    prompt_context: object,
    tool_catalog: list[dict[str, object]],
    transport_catalog: list[dict[str, object]],
    previous_results: list[dict[str, object]],
) -> str:
    prompt_context_payload = (
        prompt_context.to_dict() if hasattr(prompt_context, "to_dict") else prompt_context
    )
    return "\n".join(
        [
            "You are running inside the Nagient agent runtime.",
            "Return exactly one JSON object matching this shape:",
            (
                '{"message":"string","tool_calls":[{"call_id":"string","request":{"tool_id":"string",'
                '"function_name":"string","arguments":{},"dry_run":false,"auto_approve":false}}],'
                '"interaction_requests":[],"approval_requests":[],"notifications":[],"config_mutations":[]}'
            ),
            (
                "Use tool_calls when a tool can act or verify something. If no tool is "
                "needed, return an empty tool_calls array."
            ),
            f"Session id: {session_id}",
            f"Transport id: {transport_id}",
            "Prompt context JSON:",
            json.dumps(prompt_context_payload, ensure_ascii=False),
            "Available tools JSON:",
            json.dumps(tool_catalog, ensure_ascii=False),
            "Available transports JSON:",
            json.dumps(transport_catalog, ensure_ascii=False),
            "Previous tool results JSON:",
            json.dumps(previous_results, ensure_ascii=False),
            "Current user message:",
            user_message,
        ]
    )


def _parse_assistant_response(response_text: str) -> AssistantResponse:
    payload = _extract_json_object(response_text)
    if payload is None:
        return AssistantResponse(message=response_text.strip())
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return AssistantResponse(message=response_text.strip())
    if not isinstance(parsed, dict):
        return AssistantResponse(message=response_text.strip())
    return AssistantResponse.from_dict(parsed)


def _extract_json_object(text: str) -> str | None:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(stripped[start:], start=start):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return stripped[start : index + 1]
    return None
