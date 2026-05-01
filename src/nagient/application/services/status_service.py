from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from nagient.app.configuration import (
    activation_report_path,
    effective_config_path,
    load_runtime_configuration,
)
from nagient.app.settings import Settings
from nagient.application.services.update_service import UpdateService
from nagient.security.broker import SecretBroker
from nagient.security.workflows import WorkflowStore
from nagient.workspace.manager import WorkspaceManager


@dataclass(frozen=True)
class StatusService:
    settings: Settings
    update_service: UpdateService
    secret_broker: SecretBroker
    workflow_store: WorkflowStore
    workspace_manager: WorkspaceManager

    def collect(self) -> dict[str, object]:
        runtime_config = load_runtime_configuration(self.settings)
        payload: dict[str, object] = {
            "service": "nagient",
            "version": self.settings.version,
            "channel": self.settings.channel,
            "update_base_url": self.settings.update_base_url,
            "safe_mode": self.settings.safe_mode,
            "runtime": self._collect_runtime_state(),
            "paths": {
                "home": str(self.settings.home_dir),
                "config": str(self.settings.config_file),
                "secrets": str(self.settings.secrets_file),
                "tool_secrets": str(self.settings.tool_secrets_file),
                "plugins": str(self.settings.plugins_dir),
                "tools": str(self.settings.tools_dir),
                "providers": str(self.settings.providers_dir),
                "credentials": str(self.settings.credentials_dir),
                "state": str(self.settings.state_dir),
                "logs": str(self.settings.log_dir),
                "releases": str(self.settings.releases_dir),
            },
            "workspace": self.workspace_manager.inspect(runtime_config.workspace).to_dict(),
            "secrets": {
                "core_count": len(self.secret_broker.list_metadata("core")),
                "tool_count": len(self.secret_broker.list_metadata("tool")),
            },
            "pending_workflows": {
                "interactions": len(
                    [
                        request
                        for request in self.workflow_store.list_interactions()
                        if request.status == "pending"
                    ]
                ),
                "approvals": len(
                    [
                        request
                        for request in self.workflow_store.list_approvals()
                        if request.status == "pending"
                    ]
                ),
            },
        }

        report_path = activation_report_path(self.settings)
        if report_path.exists():
            payload["activation"] = json.loads(report_path.read_text(encoding="utf-8"))

        runtime_config_path = effective_config_path(self.settings)
        if runtime_config_path.exists():
            payload["effective_config"] = json.loads(
                runtime_config_path.read_text(encoding="utf-8")
            )

        payload["update"] = self._collect_update_status()
        return payload

    def runtime_state(self) -> dict[str, object]:
        return self._collect_runtime_state()

    def _collect_runtime_state(self) -> dict[str, object]:
        heartbeat_path = self.settings.state_dir / "heartbeat.json"
        report_path = activation_report_path(self.settings)
        heartbeat_payload: dict[str, object] = {}
        heartbeat_mtime: float | None = None
        report_mtime: float | None = None

        if heartbeat_path.exists():
            heartbeat_mtime = heartbeat_path.stat().st_mtime
            try:
                raw_payload = json.loads(heartbeat_path.read_text(encoding="utf-8"))
                if isinstance(raw_payload, dict):
                    heartbeat_payload = raw_payload
            except Exception:
                heartbeat_payload = {}

        if report_path.exists():
            report_mtime = report_path.stat().st_mtime

        latest_change = self._latest_runtime_input_change()
        latest_change_mtime = latest_change[1] if latest_change is not None else None
        latest_change_path = latest_change[0] if latest_change is not None else None
        now = time.time()
        grace_seconds = max(self.settings.heartbeat_interval_seconds * 2, 20)

        runtime_status = "stopped"
        if heartbeat_mtime is not None:
            runtime_status = "running" if now - heartbeat_mtime <= grace_seconds else "stale"

        started_at_epoch = heartbeat_payload.get("started_at_epoch")
        runtime_started_at = (
            float(started_at_epoch) if isinstance(started_at_epoch, (int, float)) else None
        )
        if runtime_started_at is None and heartbeat_mtime is not None:
            runtime_started_at = heartbeat_mtime

        needs_reconcile = bool(
            latest_change_mtime is not None
            and (report_mtime is None or latest_change_mtime > report_mtime)
        )
        needs_restart = bool(
            runtime_status == "running"
            and latest_change_mtime is not None
            and runtime_started_at is not None
            and latest_change_mtime > runtime_started_at
        )

        notes: list[str] = []
        if needs_reconcile:
            notes.append(
                "Config changed after the last activation report. "
                "Run `nagient reconcile`."
            )
        if needs_restart:
            notes.append(
                "Runtime is still using an older config snapshot. "
                "Restart it to apply changes."
            )
        if runtime_status == "stale":
            notes.append("Heartbeat is stale. The runtime may be stopped or unhealthy.")
        if runtime_status == "stopped":
            notes.append(
                "Runtime heartbeat was not found. Start the container to activate "
                "background services."
            )

        return {
            "status": runtime_status,
            "heartbeat_file": str(heartbeat_path),
            "heartbeat_updated_at": _iso_timestamp(heartbeat_mtime),
            "runtime_started_at": (
                _iso_timestamp(runtime_started_at)
                if runtime_started_at is not None
                else _as_text(heartbeat_payload.get("started_at"))
            ),
            "reported_activation_status": _as_text(heartbeat_payload.get("runtime_status")),
            "activation_report_updated_at": _iso_timestamp(report_mtime),
            "latest_change_at": _iso_timestamp(latest_change_mtime),
            "latest_change_path": str(latest_change_path) if latest_change_path is not None else "",
            "needs_reconcile": needs_reconcile,
            "needs_restart": needs_restart,
            "notes": notes,
        }

    def _collect_update_status(self) -> dict[str, object]:
        if not self.settings.update_base_url:
            return {"status": "skipped", "message": "Update center is not configured."}

        try:
            notice = self.update_service.check(
                current_version=self.settings.version,
                channel=self.settings.channel,
            )
        except Exception as exc:
            return {
                "status": "unavailable",
                "message": f"Failed to query update center: {exc}",
            }

        return {
            "status": "ready",
            "current_version": str(notice.current_version),
            "target_version": str(notice.target_version),
            "update_available": notice.update_available,
            "message": notice.message,
        }

    def _latest_runtime_input_change(self) -> tuple[Path, float] | None:
        watched_roots = [
            self.settings.config_file,
            self.settings.secrets_file,
            self.settings.tool_secrets_file,
            self.settings.credentials_dir,
            self.settings.plugins_dir,
            self.settings.providers_dir,
            self.settings.tools_dir,
        ]
        latest_path: Path | None = None
        latest_mtime = 0.0

        for root in watched_roots:
            for candidate, mtime in _iter_runtime_files(root):
                if mtime >= latest_mtime:
                    latest_path = candidate
                    latest_mtime = mtime

        if latest_path is None:
            return None
        return latest_path, latest_mtime


def _iter_runtime_files(root: Path) -> list[tuple[Path, float]]:
    if not root.exists():
        return []
    if root.is_file():
        return [(root, root.stat().st_mtime)]

    collected: list[tuple[Path, float]] = []
    for child in root.rglob("*"):
        if child.is_file():
            collected.append((child, child.stat().st_mtime))
    return collected


def _iso_timestamp(raw_timestamp: float | None) -> str:
    if raw_timestamp is None:
        return ""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(raw_timestamp))


def _as_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)
