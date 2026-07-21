# ruff: noqa: E501
from __future__ import annotations

import base64
import json
import threading
from dataclasses import replace
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import TCPServer
from typing import Any

from nagient.app.configuration import load_runtime_configuration, read_raw_config, write_raw_config
from nagient.app.settings import Settings


class _ControlPanelServer(ThreadingHTTPServer):
    """Avoid a reverse-DNS lookup while binding a local operator port."""

    def server_bind(self) -> None:
        TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = str(host)
        self.server_port = int(port)


class ControlPanel:
    """Small localhost-only operator panel for persisted runtime configuration.

    Environment variables intentionally remain outside this surface: Compose uses
    them as bootstrap and secret locks, while this panel writes only config.toml.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        status_provider: Any,
    ) -> None:
        self.settings = settings
        self.status_provider = status_provider
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        if not self.settings.control_panel_enabled:
            return False
        if not self.settings.control_panel_password:
            raise ValueError(
                "NAGIENT_CONTROL_PANEL_PASSWORD is required when the control panel is enabled."
            )
        panel = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if not panel._authorized(self):
                    return
                if self.path == "/" or self.path.startswith("/?"):
                    panel._send_html(self)
                    return
                if self.path == "/api/status":
                    panel._send_json(self, HTTPStatus.OK, panel.status_provider())
                    return
                if self.path == "/api/config":
                    panel._send_json(self, HTTPStatus.OK, panel._config_payload())
                    return
                panel._send_json(self, HTTPStatus.NOT_FOUND, {"error": "Not found."})

            def do_POST(self) -> None:  # noqa: N802
                if not panel._authorized(self):
                    return
                body = panel._read_json(self)
                if body is None:
                    return
                config = body.get("config")
                if not isinstance(config, dict):
                    panel._send_json(
                        self,
                        HTTPStatus.BAD_REQUEST,
                        {"error": "The request must contain an object in config."},
                    )
                    return
                error = panel._validate_config(config)
                if error:
                    panel._send_json(self, HTTPStatus.BAD_REQUEST, {"error": error})
                    return
                if self.path == "/api/config/preview":
                    panel._send_json(
                        self,
                        HTTPStatus.OK,
                        {"valid": True, "changed": config != read_raw_config(panel.settings.config_file)},
                    )
                    return
                if self.path == "/api/config/apply":
                    write_raw_config(panel.settings.config_file, config)
                    panel._send_json(
                        self,
                        HTTPStatus.OK,
                        {
                            "applied": True,
                            "restart_required": True,
                            "message": "Saved persistent configuration. Restart Nagient to apply it.",
                        },
                    )
                    return
                panel._send_json(self, HTTPStatus.NOT_FOUND, {"error": "Not found."})

            def log_message(self, format: str, *args: object) -> None:
                del format, args

        self._server = _ControlPanelServer(
            (self.settings.control_panel_bind_address, self.settings.control_panel_port),
            Handler,
        )
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="nagient-control-panel",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._server = None
        self._thread = None

    def _authorized(self, handler: BaseHTTPRequestHandler) -> bool:
        expected = base64.b64encode(
            f"nagient:{self.settings.control_panel_password}".encode()
        ).decode("ascii")
        if handler.headers.get("Authorization") == f"Basic {expected}":
            return True
        handler.send_response(HTTPStatus.UNAUTHORIZED)
        handler.send_header("WWW-Authenticate", 'Basic realm="Nagient"')
        handler.end_headers()
        return False

    def _read_json(self, handler: BaseHTTPRequestHandler) -> dict[str, object] | None:
        try:
            length = int(handler.headers.get("Content-Length", "0"))
            raw = handler.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(handler, HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON."})
            return None
        if not isinstance(payload, dict):
            self._send_json(handler, HTTPStatus.BAD_REQUEST, {"error": "JSON must be an object."})
            return None
        return {str(key): value for key, value in payload.items()}

    def _validate_config(self, config: dict[str, object]) -> str | None:
        temporary = self.settings.state_dir / "control-panel-validation.toml"
        try:
            write_raw_config(temporary, config)
            load_runtime_configuration(replace(self.settings, config_file=temporary))
        except Exception as exc:
            return str(exc)
        finally:
            temporary.unlink(missing_ok=True)
        return None

    def _config_payload(self) -> dict[str, object]:
        locked = sorted(
            key
            for key in __import__("os").environ
            if key.startswith(
                ("NAGIENT_AGENT", "NAGIENT_PROVIDER__", "NAGIENT_TRANSPORT__", "NAGIENT_TOOL__")
            )
        )
        return {"config": read_raw_config(self.settings.config_file), "locked_by_environment": locked}

    @staticmethod
    def _send_json(
        handler: BaseHTTPRequestHandler,
        status: HTTPStatus,
        payload: dict[str, object],
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    def _send_html(self, handler: BaseHTTPRequestHandler) -> None:
        body = _PANEL_HTML.encode("utf-8")
        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)


_PANEL_HTML = """<!doctype html><meta charset=utf-8><title>Nagient Control</title>
<style>body{font:14px system-ui;margin:32px;max-width:1000px}textarea{width:100%;height:520px;font:12px ui-monospace}button{margin:12px 8px 12px 0;padding:8px 12px}pre{white-space:pre-wrap}</style>
<h1>Nagient Control</h1><pre id=status>Loading status...</pre><textarea id=config spellcheck=false></textarea><br><button onclick="save('/api/config/preview')">Validate</button><button onclick="save('/api/config/apply')">Apply and restart later</button><pre id=result></pre>
<script>
async function load(){let[s,c]=await Promise.all([fetch('/api/status'),fetch('/api/config')]);status.textContent=JSON.stringify(await s.json(),null,2);let p=await c.json();config.value=JSON.stringify(p.config,null,2);result.textContent=p.locked_by_environment.length?'Locked by environment:\n'+p.locked_by_environment.join('\n'):''}async function save(path){try{let r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({config:JSON.parse(config.value)})});result.textContent=JSON.stringify(await r.json(),null,2)}catch(e){result.textContent=e.message}}load()
</script>"""
