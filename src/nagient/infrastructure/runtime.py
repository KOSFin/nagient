from __future__ import annotations

import json
import signal
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nagient.app.configuration import (
    RuntimeConfiguration,
    TransportInstanceConfig,
    load_runtime_configuration,
)
from nagient.app.settings import Settings
from nagient.domain.entities.system_state import ActivationReport
from nagient.plugins.base import BaseTransportPlugin, TransportRuntimeContext
from nagient.plugins.registry import TransportPluginRegistry
from nagient.workspace.manager import WorkspaceLayout, WorkspaceManager


@dataclass
class _StartedTransport:
    config: TransportInstanceConfig
    implementation: BaseTransportPlugin
    poll_stop_event: threading.Event | None = None
    poll_thread: threading.Thread | None = None


@dataclass
class RuntimeAgent:
    settings: Settings
    activation_runner: Callable[[], ActivationReport] | None = None
    plugin_registry: TransportPluginRegistry = field(default_factory=TransportPluginRegistry)
    inbound_message_handler: Callable[[str, dict[str, object]], str | None] | None = None
    workspace_manager: WorkspaceManager | None = None
    scheduler_service: Any | None = None
    scheduled_job_handler: Callable[[Any], str | None] | None = None

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
        started_transports: list[_StartedTransport] = []
        scheduler_layout = self._scheduler_layout(runtime_config)
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
                self._run_due_jobs(log_path, scheduler_layout)
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
    ) -> list[_StartedTransport]:
        discovered = self.plugin_registry.discover(self.settings.plugins_dir)
        ready_by_id = {
            transport.transport_id: transport
            for transport in (activation_report.transports if activation_report else [])
        }
        started: list[_StartedTransport] = []

        for issue in discovered.issues:
            self._log(log_path, f"Transport discovery issue: {issue.message}")

        for transport in runtime_config.transports:
            if not transport.enabled:
                continue

            transport_state = ready_by_id.get(transport.transport_id)
            if transport_state is not None and transport_state.status not in {
                "ready",
                "degraded",
            }:
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
                runtime_state_dir = (
                    self.settings.state_dir / "transports" / transport.transport_id
                )
                def _runtime_log(
                    message: str,
                    *,
                    _transport_id: str = transport.transport_id,
                ) -> None:
                    self._log(log_path, self._format_transport_log(_transport_id, message))

                plugin.implementation.bind_runtime(
                    transport.transport_id,
                    TransportRuntimeContext(
                        state_dir=runtime_state_dir,
                        log=_runtime_log,
                    ),
                )
                plugin.implementation.start(
                    transport.transport_id,
                    transport.config,
                    runtime_config.secrets,
                )
                started_transport = _StartedTransport(
                    config=transport,
                    implementation=plugin.implementation,
                )
                if self._should_spawn_poll_thread(plugin.implementation):
                    poll_stop_event = threading.Event()
                    poll_thread = threading.Thread(
                        target=self._poll_transport_loop,
                        name=f"nagient-transport-{transport.transport_id}",
                        args=(
                            log_path,
                            transport,
                            plugin.implementation,
                            runtime_config.secrets,
                            poll_stop_event,
                        ),
                        daemon=True,
                    )
                    started_transport.poll_stop_event = poll_stop_event
                    started_transport.poll_thread = poll_thread
                    poll_thread.start()
                started.append(started_transport)
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
        started_transports: list[_StartedTransport],
    ) -> None:
        for started_transport in reversed(started_transports):
            transport = started_transport.config
            implementation = started_transport.implementation
            if started_transport.poll_stop_event is not None:
                started_transport.poll_stop_event.set()
            if started_transport.poll_thread is not None:
                started_transport.poll_thread.join(timeout=2.0)
            try:
                implementation.stop(transport.transport_id)
                self._log(log_path, f"Transport {transport.transport_id} stopped.")
            except Exception as exc:
                self._log(
                    log_path,
                    f"Transport {transport.transport_id} failed to stop cleanly: {exc}",
                )

    def _should_spawn_poll_thread(self, implementation: BaseTransportPlugin) -> bool:
        return (
            implementation.__class__.poll_inbound_events
            is not BaseTransportPlugin.poll_inbound_events
        )

    def _poll_transport_loop(
        self,
        log_path: Path,
        transport: TransportInstanceConfig,
        implementation: BaseTransportPlugin,
        secrets: dict[str, str],
        stop_event: threading.Event,
    ) -> None:
        while not stop_event.is_set():
            try:
                raw_events = implementation.poll_inbound_events(
                    transport.transport_id,
                    transport.config,
                    secrets,
                )
            except Exception as exc:
                self._log(
                    log_path,
                    f"Transport {transport.transport_id} poll failed: {exc}",
                )
                stop_event.wait(timeout=2.0)
                continue

            handled_any = False
            for raw_event in raw_events:
                handled_any = True
                self._handle_polled_transport_event(
                    log_path,
                    transport,
                    implementation,
                    secrets,
                    raw_event,
                )

            if not handled_any:
                stop_event.wait(timeout=0.5)

    def _handle_polled_transport_event(
        self,
        log_path: Path,
        transport: TransportInstanceConfig,
        implementation: BaseTransportPlugin,
        secrets: dict[str, str],
        raw_event: object,
    ) -> None:
        try:
            normalized = implementation.normalize_inbound_event(raw_event)
        except Exception as exc:
            self._log(
                log_path,
                f"Transport {transport.transport_id} failed to normalize inbound event: {exc}",
            )
            return

        event_type = str(normalized.get("event_type", "")).strip().lower()
        if event_type not in {"message", "callback_query", "edited_message"}:
            return

        text = str(normalized.get("text", "")).strip()
        if not text:
            return

        reply_target = normalized.get("reply_target")
        if not isinstance(reply_target, dict):
            self._log(
                log_path,
                self._format_transport_log(
                    transport.transport_id,
                    "produced a message event without reply_target.",
                ),
            )
            return

        if self.inbound_message_handler is None:
            self._log(
                log_path,
                self._format_transport_log(
                    transport.transport_id,
                    "received a message but no handler is configured.",
                ),
            )
            return

        reply_text: str | None
        try:
            reply_text = self.inbound_message_handler(transport.transport_id, normalized)
        except Exception as exc:
            reply_text = f"Nagient error: {exc}"
            self._log(
                log_path,
                f"Transport {transport.transport_id} handler failed: {exc}",
            )

        if not reply_text:
            return

        reply_payload = dict(reply_target)
        reply_payload["text"] = reply_text
        reply_payload["_transport_config"] = dict(transport.config)
        reply_payload["_transport_id"] = transport.transport_id
        secret_name = transport.config.get("bot_token_secret")
        if (
            transport.plugin_id == "builtin.telegram"
            and isinstance(secret_name, str)
            and secret_name in secrets
        ):
            reply_payload["_token"] = secrets[secret_name]

        try:
            implementation.send_message(reply_payload)
        except Exception as exc:
            self._log(
                log_path,
                f"Transport {transport.transport_id} failed to send a reply: {exc}",
            )

    def _format_transport_log(self, transport_id: str, message: str) -> str:
        return f"Transport {transport_id}: {message}"

    def _transport_start_message(self, transport: TransportInstanceConfig) -> str:
        if transport.transport_id == "telegram":
            default_chat_id = str(transport.config.get("default_chat_id", "")).strip()
            if default_chat_id:
                return (
                    "Transport telegram loaded with live polling enabled. "
                    f"Default outbound chat is {default_chat_id}."
                )
            return (
                "Transport telegram loaded with live polling enabled. "
                "Inbound replies use the chat id from each message."
            )
        if transport.transport_id == "webhook":
            path = str(transport.config.get("path", "/events")).strip() or "/events"
            port = transport.config.get("listen_port", 8080)
            return (
                "Transport webhook loaded in helper-only mode with path "
                f"{path} on port {port}. The built-in plugin does not open an HTTP listener "
                "on its own yet."
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

    def _scheduler_layout(
        self,
        runtime_config: RuntimeConfiguration,
    ) -> WorkspaceLayout | None:
        if self.workspace_manager is None or self.scheduler_service is None:
            return None
        return self.workspace_manager.ensure_layout(runtime_config.workspace)

    def _run_due_jobs(
        self,
        log_path: Path,
        layout: WorkspaceLayout | None,
    ) -> None:
        if (
            layout is None
            or self.scheduler_service is None
            or self.scheduled_job_handler is None
        ):
            return
        try:
            executed = self.scheduler_service.run_due_jobs(
                layout,
                self.scheduled_job_handler,
            )
        except Exception as exc:
            self._log(log_path, f"Scheduler failed while running due jobs: {exc}")
            return
        for job in executed:
            self._log(
                log_path,
                f"Scheduler executed job {job.job_id} ({job.trigger}).",
            )


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
