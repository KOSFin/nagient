from __future__ import annotations

import getpass
import time
from dataclasses import dataclass

from nagient.app.configuration import RuntimeConfiguration, load_runtime_configuration
from nagient.app.settings import Settings
from nagient.domain.entities.system_state import CredentialRecord
from nagient.providers.base import LoadedProviderPlugin
from nagient.providers.manager import ProviderManager
from nagient.providers.registry import ProviderPluginRegistry
from nagient.providers.storage import AuthSessionStore, FileCredentialStore


@dataclass(frozen=True)
class ProviderService:
    settings: Settings
    provider_registry: ProviderPluginRegistry
    provider_manager: ProviderManager
    credential_store: FileCredentialStore
    auth_session_store: AuthSessionStore

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

        provider_config, plugin = self._resolve_provider(runtime_config, discovery.plugins, provider_id)
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
        provider_config, plugin = self._resolve_provider(runtime_config, discovery.plugins, provider_id)
        if "list_models" not in plugin.manifest.capabilities:
            raise ValueError(
                f"Provider plugin {plugin.manifest.plugin_id!r} does not support model discovery."
            )
        credential = self.credential_store.load(provider_config.provider_id)
        models = plugin.implementation.list_models(
            provider_config.provider_id,
            provider_config.config,
            runtime_config.secrets,
            credential,
        )
        return {
            "provider_id": provider_config.provider_id,
            "plugin_id": provider_config.plugin_id,
            "models": [model.to_dict() for model in models],
        }

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
        provider_config, plugin = self._resolve_provider(runtime_config, discovery.plugins, provider_id)
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
                resolved_secret_name = self._secret_name(provider_config.config, plugin, secret_name)
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
            resolved_secret_name = self._secret_name(provider_config.config, plugin, secret_name)
            if resolved_secret_name is None:
                raise ValueError(
                    f"Provider {provider_id!r} does not define api_key_secret and has no "
                    "built-in default secret name."
                )
            _upsert_secret_value(self.settings.secrets_file, resolved_secret_name, resolved_api_key)
            reloaded_runtime_config = load_runtime_configuration(self.settings)
            state = self._inspect_provider(reloaded_runtime_config, plugin, provider_id)
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
        provider_config, plugin = self._resolve_provider(runtime_config, discovery.plugins, provider_id)
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
        return {
            "provider": state.to_dict(),
            "credential_path": str(path),
        }

    def logout(self, provider_id: str) -> dict[str, object]:
        runtime_config = load_runtime_configuration(self.settings)
        discovery = self.provider_registry.discover(self.settings.providers_dir)
        provider_config, plugin = self._resolve_provider(runtime_config, discovery.plugins, provider_id)
        auth_mode = _auth_mode(provider_config.config, plugin.manifest.default_auth_mode)
        credential = self.credential_store.load(provider_id)
        plugin.implementation.logout(provider_id, provider_config.config, credential)
        deleted = self.credential_store.delete(provider_id)
        deleted_secret = False
        if auth_mode == "api_key":
            secret_name = self._secret_name(provider_config.config, plugin, None)
            if secret_name is not None:
                deleted_secret = _remove_secret_value(self.settings.secrets_file, secret_name)
        reloaded_runtime_config = load_runtime_configuration(self.settings)
        state = self._inspect_provider(reloaded_runtime_config, plugin, provider_id)
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
    ):
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
    ):
        provider_config = next(
            (provider for provider in runtime_config.providers if provider.provider_id == provider_id),
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


def _upsert_secret_value(secrets_file, key: str, value: str) -> None:
    secrets_file.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if secrets_file.exists():
        lines = secrets_file.read_text(encoding="utf-8").splitlines()

    serialized = f"{key}={_serialize_env_value(value)}"
    updated = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("export "):
            stripped = stripped[7:].strip()
        if not stripped or "=" not in stripped:
            continue
        candidate_key = stripped.split("=", 1)[0].strip()
        if candidate_key == key:
            lines[index] = serialized
            updated = True
            break

    if not updated:
        lines.append(serialized)

    secrets_file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _remove_secret_value(secrets_file, key: str) -> bool:
    if not secrets_file.exists():
        return False
    lines = secrets_file.read_text(encoding="utf-8").splitlines()
    kept_lines: list[str] = []
    removed = False
    for line in lines:
        stripped = line.strip()
        normalized = stripped[7:].strip() if stripped.startswith("export ") else stripped
        if normalized and "=" in normalized and normalized.split("=", 1)[0].strip() == key:
            removed = True
            continue
        kept_lines.append(line)
    if removed:
        secrets_file.write_text("\n".join(kept_lines).rstrip() + "\n", encoding="utf-8")
    return removed


def _serialize_env_value(value: str) -> str:
    if not value or any(char.isspace() for char in value) or "#" in value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value
