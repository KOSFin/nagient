from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.bootstrap import PROJECT_ROOT


class RenderBootstrapAssetsTests(unittest.TestCase):
    def test_renderer_replaces_bootstrap_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            subprocess.run(
                [
                    sys.executable,
                    "scripts/release/render_bootstrap_assets.py",
                    "--output-dir",
                    str(output_dir),
                    "--update-base-url",
                    "https://updates.your-domain.tld",
                ],
                cwd=PROJECT_ROOT,
                check=True,
            )

            install_script = (output_dir / "install.sh").read_text(encoding="utf-8")
            install_powershell = (output_dir / "install.ps1").read_text(encoding="utf-8")

            self.assertIn("https://updates.your-domain.tld", install_script)
            self.assertNotIn("__NAGIENT_UPDATE_BASE_URL__", install_script)
            self.assertIn("https://updates.your-domain.tld", install_powershell)
            self.assertNotIn("__NAGIENT_UPDATE_BASE_URL__", install_powershell)


if __name__ == "__main__":
    unittest.main()
