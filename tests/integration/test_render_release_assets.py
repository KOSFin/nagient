from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.bootstrap import PROJECT_ROOT


class RenderReleaseAssetsTests(unittest.TestCase):
    def test_renderer_replaces_release_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            subprocess.run(
                [
                    sys.executable,
                    "scripts/release/render_release_assets.py",
                    "--output-dir",
                    str(output_dir),
                    "--update-base-url",
                    "https://updates.your-domain.tld",
                    "--docker-image",
                    "docker.io/mydockerhub/nagient:1.0.0",
                    "--default-channel",
                    "stable",
                    "--docker-project-name",
                    "nagient",
                    "--container-name",
                    "nagient",
                ],
                cwd=PROJECT_ROOT,
                check=True,
            )

            install_script = (output_dir / "install.sh").read_text(encoding="utf-8")
            compose_file = (output_dir / "docker-compose.yml").read_text(encoding="utf-8")

            self.assertIn("https://updates.your-domain.tld", install_script)
            self.assertNotIn("__NAGIENT_UPDATE_BASE_URL__", install_script)
            self.assertIn("docker.io/mydockerhub/nagient:1.0.0", compose_file)
            self.assertNotIn("__NAGIENT_DOCKER_IMAGE__", compose_file)


if __name__ == "__main__":
    unittest.main()

