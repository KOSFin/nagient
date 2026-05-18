from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from nagient.domain.entities.system_state import CheckIssue
from nagient.tools.base import BaseToolPlugin, ToolExecutionContext, ToolRiskDecision


class ExternalProcessToolPlugin(BaseToolPlugin):
    def __init__(self, *, command: list[str], cwd: Path, timeout_seconds: int = 30) -> None:
        self._command = command
        self._cwd = cwd
        self._timeout_seconds = timeout_seconds

    def validate_config(
        self,
        tool_id: str,
        config: Mapping[str, object],
        secret_broker: object,
    ) -> list[CheckIssue]:
        del config, secret_broker
        if not self._command:
            return [
                CheckIssue(
                    severity="error",
                    code="tool.external.missing_command",
                    message=f"Tool {tool_id!r} does not define an external command.",
                    source=tool_id,
                )
            ]
        return []

    def self_test(
        self,
        tool_id: str,
        config: Mapping[str, object],
        secret_broker: object,
    ) -> list[CheckIssue]:
        del config, secret_broker
        try:
            result = self._call(
                "selftest",
                {"tool_id": tool_id},
                timeout_seconds=min(self._timeout_seconds, 10),
            )
        except Exception as exc:
            return [
                CheckIssue(
                    severity="error",
                    code="tool.external.selftest_failed",
                    message=f"External tool selftest failed: {exc}",
                    source=tool_id,
                )
            ]
        return _issues_from_payload(result.get("issues"), source=tool_id)

    def healthcheck(
        self,
        tool_id: str,
        config: Mapping[str, object],
        secret_broker: object,
    ) -> list[CheckIssue]:
        del config, secret_broker
        try:
            result = self._call(
                "healthcheck",
                {"tool_id": tool_id},
                timeout_seconds=min(self._timeout_seconds, 10),
            )
        except Exception:
            return []
        return _issues_from_payload(result.get("issues"), source=tool_id)

    def assess_risk(
        self,
        function_name: str,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> ToolRiskDecision:
        del function_name, arguments, context
        return ToolRiskDecision(approval_policy="inherit")

    def __getattr__(self, name: str) -> object:
        if name.startswith("_"):
            raise AttributeError(name)

        def _binding(arguments: Mapping[str, object], context: ToolExecutionContext) -> dict[str, Any]:
            return self.execute(name, arguments, context)

        return _binding

    def execute(
        self,
        function_name: str,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        payload = {
            "tool_id": context.tool_id,
            "plugin_id": context.plugin_id,
            "function_name": function_name,
            "arguments": dict(arguments),
            "config": dict(context.config),
            "workspace": {
                "root": str(context.workspace.root),
                "mode": context.workspace.config.mode,
                "workspace_id": context.workspace.metadata.workspace_id,
            },
            "dry_run": context.dry_run,
            "session_id": context.session_id,
            "transport_id": context.transport_id,
            "checkpoint_id": context.checkpoint_id,
        }
        result = self._call("execute", payload, timeout_seconds=self._timeout_seconds)
        output = result.get("output", result)
        if not isinstance(output, dict):
            raise ValueError("External tool response must contain an object output.")
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
            raise ValueError("External tool must write a JSON object to stdout.")
        status = str(decoded.get("status", "success"))
        if status in {"error", "failed"}:
            message = str(decoded.get("message", "External tool failed."))
            raise ValueError(message)
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
                code=str(item.get("code", "tool.external.issue")),
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
