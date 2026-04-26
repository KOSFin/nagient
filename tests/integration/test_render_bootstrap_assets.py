from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.bootstrap import PROJECT_ROOT

BASE_URL = "https://updates.your-domain.tld"


def _write_mock_curl(fake_bin: Path) -> None:
    mock_curl = fake_bin / "curl"
    mock_curl.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        'mapping_path = Path(os.environ["NAGIENT_TEST_URL_MAP"])\n'
        'mapping = json.loads(mapping_path.read_text(encoding="utf-8"))\n'
        "url = sys.argv[-1]\n"
        'sys.stdout.write(Path(mapping[url]).read_text(encoding="utf-8"))\n',
        encoding="utf-8",
    )
    mock_curl.chmod(0o755)


def _isolated_script_env(*, path_prefix: Path, mapping_path: Path) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "NAGIENT_CHANNEL",
            "NAGIENT_HOME",
            "NAGIENT_UPDATE_BASE_URL",
            "UPDATE_BASE_URL",
        }
    }
    env["NAGIENT_TEST_URL_MAP"] = str(mapping_path)
    env["PATH"] = f"{path_prefix}{os.pathsep}{env['PATH']}"
    return env


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
                    BASE_URL,
                ],
                cwd=PROJECT_ROOT,
                check=True,
            )

            install_script = (output_dir / "install.sh").read_text(encoding="utf-8")
            install_powershell = (output_dir / "install.ps1").read_text(encoding="utf-8")

            self.assertIn(BASE_URL, install_script)
            self.assertNotIn("__NAGIENT_UPDATE_BASE_URL__", install_script)
            self.assertIn(BASE_URL, install_powershell)
            self.assertNotIn("__NAGIENT_UPDATE_BASE_URL__", install_powershell)

    def test_rendered_bootstrap_installer_executes_against_mock_update_center(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "out"
            subprocess.run(
                [
                    sys.executable,
                    "scripts/release/render_bootstrap_assets.py",
                    "--output-dir",
                    str(output_dir),
                    "--update-base-url",
                    BASE_URL,
                ],
                cwd=PROJECT_ROOT,
                check=True,
            )

            fixtures_dir = Path(temp_dir) / "fixtures"
            fake_bin = Path(temp_dir) / "bin"
            fixtures_dir.mkdir()
            fake_bin.mkdir()

            channel_payload = fixtures_dir / "channel.json"
            versioned_installer = fixtures_dir / "install.sh"
            channel_payload.write_text('{"latest_version":"9.9.9"}\n', encoding="utf-8")
            versioned_installer.write_text(
                "#!/usr/bin/env bash\n"
                "echo BOOTSTRAP_OK\n",
                encoding="utf-8",
            )

            url_map = {
                f"{BASE_URL}/channels/stable.json": str(channel_payload),
                f"{BASE_URL}/9.9.9/install.sh": str(versioned_installer),
            }
            mapping_path = fixtures_dir / "url-map.json"
            mapping_path.write_text(json.dumps(url_map), encoding="utf-8")
            _write_mock_curl(fake_bin)

            env = _isolated_script_env(path_prefix=fake_bin, mapping_path=mapping_path)

            process = subprocess.run(
                ["bash", str(output_dir / "install.sh")],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            self.assertIn("BOOTSTRAP_OK", process.stdout)


if __name__ == "__main__":
    unittest.main()
