from __future__ import annotations

import json
from dataclasses import dataclass

from nagient.app.configuration import activation_report_path, effective_config_path
from nagient.app.settings import Settings
from nagient.application.services.update_service import UpdateService


@dataclass(frozen=True)
class StatusService:
    settings: Settings
    update_service: UpdateService

    def collect(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "service": "nagient",
            "version": self.settings.version,
            "channel": self.settings.channel,
            "update_base_url": self.settings.update_base_url,
            "safe_mode": self.settings.safe_mode,
            "paths": {
                "home": str(self.settings.home_dir),
                "config": str(self.settings.config_file),
                "secrets": str(self.settings.secrets_file),
                "plugins": str(self.settings.plugins_dir),
                "state": str(self.settings.state_dir),
                "logs": str(self.settings.log_dir),
                "releases": str(self.settings.releases_dir),
            },
        }

        report_path = activation_report_path(self.settings)
        if report_path.exists():
            payload["activation"] = json.loads(report_path.read_text(encoding="utf-8"))

        runtime_config_path = effective_config_path(self.settings)
        if runtime_config_path.exists():
            payload["effective_config"] = json.loads(runtime_config_path.read_text(encoding="utf-8"))

        payload["update"] = self._collect_update_status()
        return payload

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
