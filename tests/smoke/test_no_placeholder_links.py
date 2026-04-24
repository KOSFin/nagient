from __future__ import annotations

import unittest
from pathlib import Path

from tests.bootstrap import PROJECT_ROOT


class NoPlaceholderLinksTests(unittest.TestCase):
    def test_repository_text_files_do_not_use_old_scaffold_placeholders(self) -> None:
        banned_fragments = [
            "https://updates.example.com",
            "docker.io/example/",
            "https://github.com/OWNER/REPO",
            "https://OWNER.github.io/REPO",
        ]
        scan_roots = [
            PROJECT_ROOT / ".github",
            PROJECT_ROOT / "ai",
            PROJECT_ROOT / "config",
            PROJECT_ROOT / "developer",
            PROJECT_ROOT / "docker",
            PROJECT_ROOT / "docs",
            PROJECT_ROOT / "metadata",
            PROJECT_ROOT / "scripts",
            PROJECT_ROOT / "src",
            PROJECT_ROOT / "tests",
            PROJECT_ROOT / "README.md",
            PROJECT_ROOT / "README.ru.md",
            PROJECT_ROOT / "pyproject.toml",
            PROJECT_ROOT / "Makefile",
            PROJECT_ROOT / "Dockerfile",
        ]

        text_files: list[Path] = []
        for root in scan_roots:
            if root.is_file():
                text_files.append(root)
                continue
            text_files.extend(
                path
                for path in root.rglob("*")
                if path.is_file() and "__pycache__" not in path.parts
            )

        violations: list[str] = []
        for path in text_files:
            if path.name == "test_no_placeholder_links.py":
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            for fragment in banned_fragments:
                if fragment in content:
                    violations.append(f"{path.relative_to(PROJECT_ROOT)} -> {fragment}")

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
