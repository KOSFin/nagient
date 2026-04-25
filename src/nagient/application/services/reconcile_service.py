from __future__ import annotations

import json
from dataclasses import dataclass

from nagient.app.configuration import (
    activation_report_path,
    effective_config_path,
    last_known_good_path,
    load_runtime_configuration,
)
from nagient.app.settings import Settings
from nagient.application.services.preflight_service import PreflightService
from nagient.domain.entities.system_state import ActivationReport
from nagient.workspace.manager import WorkspaceManager


@dataclass(frozen=True)
class ReconcileService:
    settings: Settings
    preflight_service: PreflightService
    workspace_manager: WorkspaceManager

    def reconcile(self) -> ActivationReport:
        self.settings.ensure_directories()
        report = self.preflight_service.inspect()
        runtime_config = load_runtime_configuration(self.settings)
        if report.workspace is None or report.workspace.status != "failed":
            self.workspace_manager.ensure_layout(runtime_config.workspace)

        report_path = activation_report_path(self.settings)
        report_path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")

        if report.can_activate:
            effective_payload = json.dumps(report.effective_config, indent=2) + "\n"
            effective_config_path(self.settings).write_text(
                effective_payload,
                encoding="utf-8",
            )
            last_known_good_path(self.settings).write_text(effective_payload, encoding="utf-8")

        return report
