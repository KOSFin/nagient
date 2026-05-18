from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

from nagient.domain.entities.system_state import CheckIssue
from nagient.plugins.base import BaseTransportPlugin, TransportRuntimeContext


class ExternalProcessTransportPlugin(BaseTransportPlugin):
    def __init__(self, *, command: list[str], cwd: Path, timeout_seconds: int = 30) -> None:
        self._command = command
        self._cwd = cwd
        self._timeout_seconds = timeout_seconds
        self._runtime_contexts: dict[str, TransportRuntimeContext] = {}
        self._runtime_configs: dict[str, dict[str, object]] = {}
        self._runtime_secrets: dict[str, dict[str, str]] = {}

    def validate_config(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        try:
            result = self._call(
                "validate_config",
                {"transport_id": transport_id, "config": dict(config), "secrets": dict(secrets)},
                timeout_seconds=min(self._timeout_seconds, 10),
            )
        except Exception as exc:
            return [
                CheckIssue(
                    severity="error",
                    code="transport.external.validate_failed",
                    message=f"External transport validation failed: {exc}",
                    source=transport_id,
                )
            ]
        return _issues_from_payload(result.get("issues"), source=transport_id)

    def self_test(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        try:
            result = self._call(
                "selftest",
                {"transport_id": transport_id, "config": dict(config), "secrets": dict(secrets)},
                timeout_seconds=min(self._timeout_seconds, 10),
            )
        except Exception as exc:
            return [
                CheckIssue(
                    severity="error",
                    code="transport.external.selftest_failed",
                    message=f"External transport selftest failed: {exc}",
                    source=transport_id,
                )
            ]
        return _issues_from_payload(result.get("issues"), source=transport_id)

    def healthcheck(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        try:
            result = self._call(
                "healthcheck",
                {"transport_id": transport_id, "config": dict(config), "secrets": dict(secrets)},
                timeout_seconds=min(self._timeout_seconds, 10),
            )
        except Exception:
            return []
        return _issues_from_payload(result.get("issues"), source=transport_id)

    def bind_runtime(
        self,
        transport_id: str,
        runtime: TransportRuntimeContext,
    ) -> None:
        self._runtime_contexts[transport_id] = runtime

    def send_message(self, payload: dict[str, object]) -> dict[str, object]:
        return self._payload_call("send_message", payload)

    def send_notification(self, payload: dict[str, object]) -> dict[str, object]:
        return self._payload_call("send_notification", payload)

    def normalize_inbound_event(self, payload: object) -> dict[str, object]:
        result = self._call(
            "normalize_inbound_event",
            {"payload": payload},
            timeout_seconds=self._timeout_seconds,
        )
        normalized = result.get("output", result)
        if not isinstance(normalized, dict):
            raise ValueError("External transport normalize_inbound_event must return an object.")
        return {str(key): value for key, value in normalized.items()}

    def poll_inbound_events(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[object]:
        result = self._call(
            "poll_inbound_events",
            {"transport_id": transport_id, "config": dict(config), "secrets": dict(secrets)},
            timeout_seconds=self._timeout_seconds,
        )
        output = result.get("output", result.get("events", []))
        return list(output) if isinstance(output, list) else []

    def start(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> None:
        self._runtime_configs[transport_id] = dict(config)
        self._runtime_secrets[transport_id] = dict(secrets)
        self._call(
            "start",
            {"transport_id": transport_id, "config": dict(config), "secrets": dict(secrets)},
            timeout_seconds=self._timeout_seconds,
        )

    def stop(self, transport_id: str) -> None:
        self._call("stop", {"transport_id": transport_id}, timeout_seconds=self._timeout_seconds)
        self._runtime_configs.pop(transport_id, None)
        self._runtime_secrets.pop(transport_id, None)

    def __getattr__(self, name: str) -> object:
        if name.startswith("_"):
            raise AttributeError(name)

        def _binding(payload: dict[str, object]) -> dict[str, object]:
            return self._payload_call(name, payload)

        return _binding

    def _payload_call(self, method: str, payload: dict[str, object]) -> dict[str, object]:
        transport_id = str(payload.get("_transport_id", "")).strip()
        config = payload.get("_transport_config")
        secrets = payload.get("_transport_secrets")
        if not isinstance(config, dict):
            config = self._runtime_configs.get(transport_id, {})
        if not isinstance(secrets, dict):
            secrets = self._runtime_secrets.get(transport_id, {})
        result = self._call(
            method,
            {
                "transport_id": transport_id,
                "config": {str(key): value for key, value in config.items()},
                "secrets": {str(key): str(value) for key, value in secrets.items()},
                "payload": payload,
            },
            timeout_seconds=self._timeout_seconds,
        )
        output = result.get("output", result)
        if not isinstance(output, dict):
            raise ValueError(f"External transport {method} must return an object.")
        return {str(key): value for key, value in output.items()}

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
            raise ValueError("External transport must write a JSON object to stdout.")
        status = str(decoded.get("status", "success"))
        if status in {"error", "failed"}:
            raise ValueError(str(decoded.get("message", "External transport failed.")))
        return {str(key): value for key, value in decoded.items()}


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
                code=str(item.get("code", "transport.external.issue")),
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
