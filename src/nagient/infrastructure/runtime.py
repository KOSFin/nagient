from __future__ import annotations

import json
import signal
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from nagient.app.settings import Settings


@dataclass
class RuntimeAgent:
    settings: Settings

    def serve(self, once: bool = False) -> int:
        self.settings.ensure_directories()
        stop_event = threading.Event()
        self._register_signal_handlers(stop_event)

        heartbeat_path = self.settings.state_dir / "heartbeat.json"
        while not stop_event.is_set():
            self._write_heartbeat(heartbeat_path)
            if once:
                break
            stop_event.wait(timeout=self.settings.heartbeat_interval_seconds)

        return 0

    def _register_signal_handlers(self, stop_event: threading.Event) -> None:
        def _handle_signal(signum: int, _frame: object) -> None:
            stop_event.set()

        for current_signal in (signal.SIGINT, signal.SIGTERM):
            signal.signal(current_signal, _handle_signal)

    def _write_heartbeat(self, heartbeat_path: Path) -> None:
        payload = {
            "service": "nagient",
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "channel": self.settings.channel,
            "version": self.settings.version,
        }
        heartbeat_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
