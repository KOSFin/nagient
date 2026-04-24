from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.bootstrap import PROJECT_ROOT, SRC_ROOT


class CliManifestRenderTests(unittest.TestCase):
    def test_manifest_render_writes_expected_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "manifest.json"
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nagient",
                    "manifest",
                    "render",
                    "--version",
                    "1.2.3",
                    "--channel",
                    "stable",
                    "--base-url",
                    "https://updates.your-domain.tld",
                    "--docker-image",
                    "docker.io/mydockerhub/nagient:1.2.3",
                    "--published-at",
                    "2026-04-24T00:00:00Z",
                    "--output",
                    str(output_path),
                ],
                cwd=PROJECT_ROOT,
                env={**os.environ, "PYTHONPATH": str(SRC_ROOT)},
                capture_output=True,
                text=True,
                check=True,
            )

            stdout_payload = json.loads(process.stdout)
            file_payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(stdout_payload["version"], "1.2.3")
            self.assertEqual(file_payload["docker"]["image"], "docker.io/mydockerhub/nagient:1.2.3")
            self.assertEqual(len(file_payload["artifacts"]), 7)


if __name__ == "__main__":
    unittest.main()
