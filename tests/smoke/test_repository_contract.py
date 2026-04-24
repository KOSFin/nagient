from __future__ import annotations

import json
import unittest

from tests.bootstrap import PROJECT_ROOT


class RepositoryContractTests(unittest.TestCase):
    def test_required_top_level_files_exist(self) -> None:
        required = [
            "README.md",
            "README.ru.md",
            "pyproject.toml",
            "Dockerfile",
            ".github/workflows/auto-tag.yml",
            ".github/workflows/ci.yml",
            ".github/workflows/release.yml",
            ".github/workflows/update-center.yml",
        ]
        for relative_path in required:
            self.assertTrue((PROJECT_ROOT / relative_path).exists(), msg=relative_path)

    def test_bundled_update_center_files_are_parseable(self) -> None:
        channel_payload = json.loads(
            (PROJECT_ROOT / "metadata/update-center/channels/stable.json").read_text(
                encoding="utf-8"
            )
        )
        release_payload = json.loads(
            (PROJECT_ROOT / "metadata/update-center/manifests/0.1.0.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(channel_payload["channel"], "stable")
        self.assertEqual(release_payload["version"], "0.1.0")


if __name__ == "__main__":
    unittest.main()
