from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.bootstrap import PROJECT_ROOT


class ShellScriptSmokeTests(unittest.TestCase):
    def test_bash_scripts_have_valid_syntax(self) -> None:
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("bash is not available")

        script_paths = [
            "scripts/bootstrap/install.sh",
            "scripts/install.sh",
            "scripts/install-local.sh",
            "scripts/update.sh",
            "scripts/uninstall.sh",
            "docker/scripts/entrypoint.sh",
        ]
        subprocess.run(
            [bash, "-n", *script_paths],
            cwd=PROJECT_ROOT,
            check=True,
        )

    def test_docker_free_installer_runs_from_source_checkout(self) -> None:
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("bash is not available")
        with tempfile.TemporaryDirectory() as temp_dir:
            home = f"{temp_dir}/nagient"
            subprocess.run(
                [
                    bash,
                    "scripts/install-local.sh",
                    "--home",
                    home,
                    "--source",
                    str(PROJECT_ROOT),
                    "--python",
                    sys.executable,
                    "--no-start",
                ],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            version = subprocess.run(
                [f"{home}/bin/nagient", "version"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertRegex(version.stdout.strip(), r"^0\.9\.11$")


if __name__ == "__main__":
    unittest.main()
