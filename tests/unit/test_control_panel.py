from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from nagient.app.settings import Settings
from nagient.infrastructure.control_panel import ControlPanel


class ControlPanelTests(unittest.TestCase):
    def test_panel_requires_auth_and_persists_validated_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings.from_env(
                {
                    "NAGIENT_HOME": str(Path(temp_dir) / "home"),
                    "NAGIENT_CONTROL_PANEL_ENABLED": "true",
                    "NAGIENT_CONTROL_PANEL_PORT": "0",
                    "NAGIENT_CONTROL_PANEL_PASSWORD": "panel-secret",
                }
            )
            settings.ensure_directories()
            settings.config_file.write_text("[agent]\nmax_turns = 12\n", encoding="utf-8")
            panel = ControlPanel(settings=settings, status_provider=lambda: {"status": "ready"})
            self.assertTrue(panel.start())
            assert panel._server is not None
            url = f"http://127.0.0.1:{panel._server.server_address[1]}"
            try:
                auth = base64.b64encode(b"nagient:panel-secret").decode("ascii")
                request = Request(
                    f"{url}/api/config/apply",
                    data=json.dumps({"config": {"agent": {"max_turns": 7}}}).encode(),
                    headers={
                        "Authorization": f"Basic {auth}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urlopen(request, timeout=3) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertTrue(payload["applied"])
                self.assertIn("max_turns = 7", settings.config_file.read_text(encoding="utf-8"))
            finally:
                panel.stop()

    def test_enabled_panel_refuses_to_start_without_password(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings.from_env(
                {
                    "NAGIENT_HOME": str(Path(temp_dir) / "home"),
                    "NAGIENT_CONTROL_PANEL_ENABLED": "true",
                }
            )
            with self.assertRaisesRegex(ValueError, "CONTROL_PANEL_PASSWORD"):
                ControlPanel(settings=settings, status_provider=dict).start()


if __name__ == "__main__":
    unittest.main()
