from __future__ import annotations

import shutil
import subprocess
import unittest

from tests.bootstrap import PROJECT_ROOT


class ShellScriptSmokeTests(unittest.TestCase):
    def test_bash_scripts_have_valid_syntax(self) -> None:
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("bash is not available")

        script_paths = [
            "scripts/install.sh",
            "scripts/update.sh",
            "scripts/uninstall.sh",
            "docker/scripts/entrypoint.sh",
        ]
        subprocess.run(
            [bash, "-n", *script_paths],
            cwd=PROJECT_ROOT,
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
