from __future__ import annotations

import json
import signal
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from nagient.app.settings import Settings
from nagient.domain.entities.system_state import ActivationReport


@dataclass
class RuntimeAgent:
    settings: Settings
    activation_runner: Callable[[], ActivationReport] | None = None

    def serve(self, once: bool = False) -> int:
        self.settings.ensure_directories()
        stop_event = threading.Event()
        self._register_signal_handlers(stop_event)

        heartbeat_path = self.settings.state_dir / "heartbeat.json"
        activation_report = self.activation_runner() if self.activation_runner else None
        if activation_report and not activation_report.can_activate:
            self._write_heartbeat(heartbeat_path, activation_report)
            return 1

        while not stop_event.is_set():
            self._write_heartbeat(heartbeat_path, activation_report)
            if once:
                break
            stop_event.wait(timeout=self.settings.heartbeat_interval_seconds)

        return 0

    def _register_signal_handlers(self, stop_event: threading.Event) -> None:
        def _handle_signal(signum: int, _frame: object) -> None:
            stop_event.set()

        for current_signal in (signal.SIGINT, signal.SIGTERM):
            signal.signal(current_signal, _handle_signal)

    def _write_heartbeat(
        self,
        heartbeat_path: Path,
        activation_report: ActivationReport | None,
    ) -> None:
        payload: dict[str, object] = {
            "service": "nagient",
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "channel": self.settings.channel,
            "version": self.settings.version,
            "safe_mode": self.settings.safe_mode,
            "runtime_status": activation_report.status if activation_report else "ready",
        }
        if activation_report:
            payload["transports"] = [
                {
                    "transport_id": transport.transport_id,
                    "plugin_id": transport.plugin_id,
                    "status": transport.status,
                }
                for transport in activation_report.transports
            ]
            payload["providers"] = [
                {
                    "provider_id": provider.provider_id,
                    "plugin_id": provider.plugin_id,
                    "status": provider.status,
                    "authenticated": provider.authenticated,
                }
                for provider in activation_report.providers
            ]
            payload["tools"] = [
                {
                    "tool_id": tool.tool_id,
                    "plugin_id": tool.plugin_id,
                    "status": tool.status,
                }
                for tool in activation_report.tools
            ]
            payload["workspace"] = (
                activation_report.workspace.to_dict()
                if activation_report.workspace is not None
                else None
            )
        heartbeat_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
