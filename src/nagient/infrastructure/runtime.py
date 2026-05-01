from __future__ import annotations

import json
import signal
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from nagient.app.configuration import (
    RuntimeConfiguration,
    TransportInstanceConfig,
    load_runtime_configuration,
)
from nagient.app.settings import Settings
from nagient.domain.entities.system_state import ActivationReport
from nagient.plugins.registry import TransportPluginRegistry


@dataclass
class RuntimeAgent:
    settings: Settings
    activation_runner: Callable[[], ActivationReport] | None = None
    plugin_registry: TransportPluginRegistry = field(default_factory=TransportPluginRegistry)

    def serve(self, once: bool = False) -> int:
        self.settings.ensure_directories()
        stop_event = threading.Event()
        self._register_signal_handlers(stop_event)

        heartbeat_path = self.settings.state_dir / "heartbeat.json"
        log_path = self.settings.log_dir / "runtime.log"
        activation_report = self.activation_runner() if self.activation_runner else None
        runtime_config = load_runtime_configuration(self.settings)
        started_at_epoch = time.time()
        started_at = _iso_timestamp(started_at_epoch)
        started_transports: list[tuple[TransportInstanceConfig, object]] = []
        reload_warning_emitted = False

        self._log(
            log_path,
            f"Runtime starting (version {self.settings.version}, channel {self.settings.channel}).",
        )
        self._log_activation_summary(log_path, runtime_config, activation_report)

        try:
            started_transports = self._start_transports(
                log_path,
                runtime_config,
                activation_report,
            )
            while not stop_event.is_set():
                latest_change = _latest_runtime_input_change(self.settings)
                if (
                    latest_change is not None
                    and latest_change[1] > started_at_epoch
                    and not reload_warning_emitted
                ):
                    self._log(
                        log_path,
                        (
                            "Runtime config changed on disk after startup. "
                            "Run `nagient reconcile` and restart the runtime to apply it."
                        ),
                    )
                    reload_warning_emitted = True

                self._write_heartbeat(
                    heartbeat_path,
                    activation_report,
                    started_at=started_at,
                    started_at_epoch=started_at_epoch,
                    latest_change=latest_change,
                )
                if once:
                    break
                stop_event.wait(timeout=self.settings.heartbeat_interval_seconds)
        finally:
            self._stop_transports(log_path, started_transports)
            self._log(log_path, "Runtime stopped.")

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
        *,
        started_at: str,
        started_at_epoch: float,
        latest_change: tuple[Path, float] | None,
    ) -> None:
        payload: dict[str, object] = {
            "service": "nagient",
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "started_at": started_at,
            "started_at_epoch": started_at_epoch,
            "channel": self.settings.channel,
            "version": self.settings.version,
            "safe_mode": self.settings.safe_mode,
            "runtime_status": activation_report.status if activation_report else "ready",
        }
        if latest_change is not None:
            payload["latest_change_at"] = _iso_timestamp(latest_change[1])
            payload["latest_change_path"] = str(latest_change[0])
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

    def _log_activation_summary(
        self,
        log_path: Path,
        runtime_config: RuntimeConfiguration,
        activation_report: ActivationReport | None,
    ) -> None:
        if activation_report is None:
            self._log(log_path, "Activation report is not available yet.")
            return

        self._log(
            log_path,
            (
                f"Activation status: {activation_report.status} "
                f"(can_activate={'yes' if activation_report.can_activate else 'no'})."
            ),
        )
        self._log(
            log_path,
            f"Default provider: {runtime_config.default_provider or 'none'}.",
        )

        enabled_providers = [
            provider for provider in activation_report.providers if provider.enabled
        ]
        if enabled_providers:
            for provider in enabled_providers:
                self._log(
                    log_path,
                    (
                        f"Provider {provider.provider_id}: status={provider.status}, "
                        f"auth={provider.auth_mode}, authenticated="
                        f"{'yes' if provider.authenticated else 'no'}, "
                        f"model={provider.configured_model or 'none'}."
                    ),
                )
        else:
            self._log(log_path, "No provider profiles are enabled.")

        enabled_transports = [
            transport for transport in activation_report.transports if transport.enabled
        ]
        if enabled_transports:
            for transport in enabled_transports:
                self._log(
                    log_path,
                    f"Transport {transport.transport_id}: status={transport.status}.",
                )
        else:
            self._log(log_path, "No transport profiles are enabled.")

        for issue in activation_report.issues[:5]:
            self._log(
                log_path,
                f"Issue ({issue.severity}) [{issue.source}] {issue.message}",
            )

    def _start_transports(
        self,
        log_path: Path,
        runtime_config: RuntimeConfiguration,
        activation_report: ActivationReport | None,
    ) -> list[tuple[TransportInstanceConfig, object]]:
        discovered = self.plugin_registry.discover(self.settings.plugins_dir)
        ready_by_id = {
            transport.transport_id: transport
            for transport in (activation_report.transports if activation_report else [])
        }
        started: list[tuple[TransportInstanceConfig, object]] = []

        for issue in discovered.issues:
            self._log(log_path, f"Transport discovery issue: {issue.message}")

        for transport in runtime_config.transports:
            if not transport.enabled:
                continue

            transport_state = ready_by_id.get(transport.transport_id)
            if transport_state is not None and transport_state.status != "ready":
                self._log(
                    log_path,
                    (
                        f"Skipping transport {transport.transport_id}: "
                        f"status is {transport_state.status}."
                    ),
                )
                continue

            plugin = discovered.plugins.get(transport.plugin_id)
            if plugin is None:
                self._log(
                    log_path,
                    (
                        f"Skipping transport {transport.transport_id}: "
                        f"plugin {transport.plugin_id} was not found."
                    ),
                )
                continue

            try:
                plugin.implementation.start(
                    transport.transport_id,
                    transport.config,
                    runtime_config.secrets,
                )
                started.append((transport, plugin.implementation))
                self._log(
                    log_path,
                    self._transport_start_message(transport),
                )
            except Exception as exc:
                self._log(
                    log_path,
                    f"Transport {transport.transport_id} failed to start: {exc}",
                )

        return started

    def _stop_transports(
        self,
        log_path: Path,
        started_transports: list[tuple[TransportInstanceConfig, object]],
    ) -> None:
        for transport, implementation in reversed(started_transports):
            try:
                implementation.stop(transport.transport_id)
                self._log(log_path, f"Transport {transport.transport_id} stopped.")
            except Exception as exc:
                self._log(
                    log_path,
                    f"Transport {transport.transport_id} failed to stop cleanly: {exc}",
                )

    def _transport_start_message(self, transport: TransportInstanceConfig) -> str:
        if transport.transport_id == "telegram":
            default_chat_id = str(transport.config.get("default_chat_id", "")).strip()
            if default_chat_id:
                return (
                    "Transport telegram loaded for outbound delivery helpers. "
                    f"Default outbound chat is {default_chat_id}. "
                    "The built-in transport does not poll Telegram on its own yet."
                )
            return (
                "Transport telegram loaded for outbound delivery helpers. "
                "No default_chat_id is set, so proactive Telegram notices need a chat id "
                "from inbound context or manual config. The built-in transport does not poll "
                "Telegram on its own yet."
            )
        if transport.transport_id == "webhook":
            path = str(transport.config.get("path", "/events")).strip() or "/events"
            port = transport.config.get("listen_port", 8080)
            return (
                "Transport webhook loaded with path "
                f"{path} on port {port}. The built-in transport validates config but "
                "does not open an HTTP listener on its own yet."
            )
        if transport.transport_id == "console":
            return "Transport console loaded as the local fallback transport."
        return f"Transport {transport.transport_id} loaded."

    def _log(self, log_path: Path, message: str) -> None:
        timestamp = _iso_timestamp(time.time())
        line = f"[nagient] {timestamp} {message}"
        print(line, flush=True)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def _latest_runtime_input_change(settings: Settings) -> tuple[Path, float] | None:
    watched_roots = [
        settings.config_file,
        settings.secrets_file,
        settings.tool_secrets_file,
        settings.credentials_dir,
        settings.plugins_dir,
        settings.providers_dir,
        settings.tools_dir,
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


def _iso_timestamp(raw_timestamp: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(raw_timestamp))
