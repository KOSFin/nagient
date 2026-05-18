from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

from nagient.domain.entities.agent_runtime import AssistantResponse
from nagient.domain.entities.system_state import (
    AuthSessionState,
    CheckIssue,
    CredentialRecord,
    ProviderAuthStatus,
    ProviderModel,
)
from nagient.providers.base import BaseProviderPlugin, ProviderRuntimeContext


class ExternalProcessProviderPlugin(BaseProviderPlugin):
    def __init__(self, *, command: list[str], cwd: Path, timeout_seconds: int = 30) -> None:
        self._command = command
        self._cwd = cwd
        self._timeout_seconds = timeout_seconds
        self._runtime_contexts: dict[str, ProviderRuntimeContext] = {}

    def bind_runtime(
        self,
        provider_id: str,
        runtime: ProviderRuntimeContext,
    ) -> None:
        self._runtime_contexts[provider_id] = runtime

    def validate_config(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> list[CheckIssue]:
        result = self._safe_check(
            "validate_config",
            provider_id,
            config,
            secrets,
            credential,
        )
        return result

    def self_test(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> list[CheckIssue]:
        return self._safe_check("selftest", provider_id, config, secrets, credential)

    def healthcheck(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> list[CheckIssue]:
        return self._safe_check("healthcheck", provider_id, config, secrets, credential)

    def auth_status(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> ProviderAuthStatus:
        result = self._call(
            "auth_status",
            _provider_payload(provider_id, config, secrets, credential),
            timeout_seconds=min(self._timeout_seconds, 10),
        )
        output = result.get("output", result)
        if not isinstance(output, dict):
            raise ValueError("External provider auth_status must return an object.")
        return ProviderAuthStatus(
            authenticated=bool(output.get("authenticated", False)),
            auth_mode=str(output.get("auth_mode", "unknown")),
            status=str(output.get("status", "unknown")),
            message=str(output.get("message", "")),
            issues=_issues_from_payload(output.get("issues"), source=provider_id),
        )

    def begin_login(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> AuthSessionState:
        result = self._call(
            "begin_login",
            _provider_payload(provider_id, config, secrets, credential),
            timeout_seconds=self._timeout_seconds,
        )
        output = result.get("output", result)
        if not isinstance(output, dict):
            raise ValueError("External provider begin_login must return an object.")
        return AuthSessionState.from_dict(output)

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
        result = self._call(
            "complete_login",
            {
                **_provider_payload(provider_id, config, {}, credential),
                "session": session.to_dict(),
                "callback_url": callback_url,
                "code": code,
            },
            timeout_seconds=self._timeout_seconds,
        )
        output = result.get("output", result)
        if not isinstance(output, dict):
            raise ValueError("External provider complete_login must return an object.")
        return CredentialRecord.from_dict(output)

    def logout(
        self,
        provider_id: str,
        config: Mapping[str, object],
        credential: CredentialRecord | None,
    ) -> None:
        self._call(
            "logout",
            _provider_payload(provider_id, config, {}, credential),
            timeout_seconds=self._timeout_seconds,
        )

    def list_models(
        self,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> list[ProviderModel]:
        result = self._call(
            "list_models",
            _provider_payload(provider_id, config, secrets, credential),
            timeout_seconds=self._timeout_seconds,
        )
        output = result.get("output", result.get("models", []))
        if not isinstance(output, list):
            raise ValueError("External provider list_models must return a list.")
        return [
            ProviderModel(
                model_id=str(item.get("model_id", item.get("id", ""))),
                display_name=str(item.get("display_name", item.get("name", item.get("id", "")))),
                metadata=dict(item.get("metadata", {}))
                if isinstance(item.get("metadata"), dict)
                else {},
            )
            for item in output
            if isinstance(item, dict)
        ]

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
        result = self._call(
            "generate_message",
            {
                **_provider_payload(provider_id, config, secrets, credential),
                "message": message,
                "system_prompt": system_prompt,
            },
            timeout_seconds=self._timeout_seconds,
        )
        output = result.get("output", result)
        if isinstance(output, str):
            return output
        if isinstance(output, dict):
            return str(output.get("message", ""))
        raise ValueError("External provider generate_message must return text or an object.")

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
        result = self._call(
            "generate_assistant_response",
            {
                **_provider_payload(provider_id, config, secrets, credential),
                "message": message,
                "system_prompt": system_prompt,
                "session_id": session_id,
                "transport_id": transport_id,
                "prompt_context": prompt_context,
                "tool_catalog": tool_catalog,
                "transport_catalog": transport_catalog,
                "previous_results": previous_results,
            },
            timeout_seconds=self._timeout_seconds,
        )
        output = result.get("output", result)
        if not isinstance(output, dict):
            raise ValueError("External provider generate_assistant_response must return an object.")
        return AssistantResponse.from_dict(output)

    def _safe_check(
        self,
        method: str,
        provider_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
        credential: CredentialRecord | None,
    ) -> list[CheckIssue]:
        try:
            result = self._call(
                method,
                _provider_payload(provider_id, config, secrets, credential),
                timeout_seconds=min(self._timeout_seconds, 10),
            )
        except Exception as exc:
            return [
                CheckIssue(
                    severity="error",
                    code="provider.external.check_failed",
                    message=f"External provider {method} failed: {exc}",
                    source=provider_id,
                )
            ]
        return _issues_from_payload(result.get("issues"), source=provider_id)

    def _call(
        self,
        method: str,
        payload: dict[str, object],
        *,
        timeout_seconds: int,
    ) -> dict[str, object]:
        request = {"protocol": "nagient.process.v1", "method": method, **payload}
        process = subprocess.run(
            self._command,
            input=json.dumps(request),
            cwd=self._cwd,
            env=_process_env(),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if process.returncode != 0:
            stderr = process.stderr.strip()
            stdout = process.stdout.strip()
            raise ValueError(stderr or stdout or f"process exited {process.returncode}")
        stdout = process.stdout.strip()
        if not stdout:
            return {}
        decoded = json.loads(stdout)
        if not isinstance(decoded, dict):
            raise ValueError("External provider must write a JSON object to stdout.")
        status = str(decoded.get("status", "success"))
        if status in {"error", "failed"}:
            raise ValueError(str(decoded.get("message", "External provider failed.")))
        return {str(key): value for key, value in decoded.items()}


def _provider_payload(
    provider_id: str,
    config: Mapping[str, object],
    secrets: Mapping[str, str],
    credential: CredentialRecord | None,
) -> dict[str, object]:
    return {
        "provider_id": provider_id,
        "config": dict(config),
        "secrets": dict(secrets),
        "credential": credential.to_dict() if credential is not None else None,
    }


def _issues_from_payload(value: object, *, source: str) -> list[CheckIssue]:
    if not isinstance(value, list):
        return []
    issues: list[CheckIssue] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        issues.append(
            CheckIssue(
                severity=str(item.get("severity", "warning")),
                code=str(item.get("code", "provider.external.issue")),
                message=str(item.get("message", "")),
                source=str(item.get("source", source)),
                hint=str(item["hint"]) if "hint" in item else None,
            )
        )
    return issues


def _process_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env
