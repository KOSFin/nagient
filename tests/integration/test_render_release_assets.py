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
VERSION = "9.9.9"
DOCKER_IMAGE = "docker.io/mydockerhub/nagient:9.9.9"


def _render_release_assets(output_dir: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "scripts/release/render_release_assets.py",
            "--output-dir",
            str(output_dir),
            "--update-base-url",
            BASE_URL,
            "--docker-image",
            DOCKER_IMAGE,
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


def _write_mock_docker(fake_bin: Path) -> None:
    mock_docker = fake_bin / "docker"
    mock_docker.write_text(
        "#!/usr/bin/env bash\n"
        "exit 0\n",
        encoding="utf-8",
    )
    mock_docker.chmod(0o755)


def _write_release_fixture_map(output_dir: Path, fixtures_dir: Path) -> Path:
    channel_payload = fixtures_dir / "channel.json"
    manifest_payload = fixtures_dir / "manifest.json"
    compose_payload = fixtures_dir / "docker-compose.yml"
    update_payload = fixtures_dir / "update.sh"
    uninstall_payload = fixtures_dir / "uninstall.sh"

    channel_payload.write_text(
        json.dumps(
            {
                "channel": "stable",
                "latest_version": VERSION,
                "manifest_url": f"{BASE_URL}/manifests/{VERSION}.json",
            }
        ),
        encoding="utf-8",
    )
    manifest_payload.write_text(
        json.dumps(
            {
                "version": VERSION,
                "docker": {
                    "image": DOCKER_IMAGE,
                    "compose_url": f"{BASE_URL}/{VERSION}/docker-compose.yml",
                },
                "artifacts": [
                    {
                        "name": "update.sh",
                        "url": f"{BASE_URL}/{VERSION}/update.sh",
                    },
                    {
                        "name": "uninstall.sh",
                        "url": f"{BASE_URL}/{VERSION}/uninstall.sh",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    compose_payload.write_text(
        (output_dir / "docker-compose.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    update_payload.write_text(
        (output_dir / "update.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    uninstall_payload.write_text(
        (output_dir / "uninstall.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    url_map = {
        f"{BASE_URL}/channels/stable.json": str(channel_payload),
        f"{BASE_URL}/manifests/{VERSION}.json": str(manifest_payload),
        f"{BASE_URL}/{VERSION}/docker-compose.yml": str(compose_payload),
        f"{BASE_URL}/{VERSION}/update.sh": str(update_payload),
        f"{BASE_URL}/{VERSION}/uninstall.sh": str(uninstall_payload),
    }
    mapping_path = fixtures_dir / "url-map.json"
    mapping_path.write_text(json.dumps(url_map), encoding="utf-8")
    return mapping_path


class RenderReleaseAssetsTests(unittest.TestCase):
    def test_renderer_replaces_release_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            _render_release_assets(output_dir)

            install_script = (output_dir / "install.sh").read_text(encoding="utf-8")
            compose_file = (output_dir / "docker-compose.yml").read_text(encoding="utf-8")

            self.assertIn(BASE_URL, install_script)
            self.assertNotIn("__NAGIENT_UPDATE_BASE_URL__", install_script)
            self.assertIn(DOCKER_IMAGE, compose_file)
            self.assertNotIn("__NAGIENT_DOCKER_IMAGE__", compose_file)

    def test_rendered_release_installer_runs_with_mocked_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "out"
            fixtures_dir = Path(temp_dir) / "fixtures"
            fake_bin = Path(temp_dir) / "bin"
            home_dir = Path(temp_dir) / "home"
            _render_release_assets(output_dir)
            fixtures_dir.mkdir()
            fake_bin.mkdir()
            home_dir.mkdir()

            mapping_path = _write_release_fixture_map(output_dir, fixtures_dir)
            _write_mock_curl(fake_bin)
            _write_mock_docker(fake_bin)

            env = os.environ.copy()
            env["HOME"] = str(home_dir)
            env["NAGIENT_TEST_URL_MAP"] = str(mapping_path)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

            process = subprocess.run(
                ["bash", str(output_dir / "install.sh")],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            runtime_root = home_dir / ".nagient"
            self.assertIn("Nagient 9.9.9 installed", process.stdout)
            self.assertTrue((runtime_root / ".env").exists())
            self.assertIn(
                f"NAGIENT_UPDATE_BASE_URL={BASE_URL}",
                (runtime_root / ".env").read_text(encoding="utf-8"),
            )
            self.assertTrue((runtime_root / "releases" / "current.json").exists())

    def test_rendered_release_updater_runs_with_mocked_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "out"
            fixtures_dir = Path(temp_dir) / "fixtures"
            fake_bin = Path(temp_dir) / "bin"
            home_dir = Path(temp_dir) / "home"
            runtime_root = home_dir / ".nagient"
            releases_dir = runtime_root / "releases"
            _render_release_assets(output_dir)
            fixtures_dir.mkdir()
            fake_bin.mkdir()
            releases_dir.mkdir(parents=True)

            (releases_dir / "current.json").write_text('{"version":"9.9.8"}\n', encoding="utf-8")

            mapping_path = _write_release_fixture_map(output_dir, fixtures_dir)
            _write_mock_curl(fake_bin)
            _write_mock_docker(fake_bin)

            env = os.environ.copy()
            env["HOME"] = str(home_dir)
            env["NAGIENT_TEST_URL_MAP"] = str(mapping_path)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

            process = subprocess.run(
                ["bash", str(output_dir / "update.sh")],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            self.assertIn("Nagient upgraded: 9.9.8 -> 9.9.9", process.stdout)
            self.assertIn(
                f"NAGIENT_UPDATE_BASE_URL={BASE_URL}",
                (runtime_root / ".env").read_text(encoding="utf-8"),
            )
            self.assertIn(
                '"version": "9.9.9"',
                (releases_dir / "current.json").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
