from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote

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

    def test_markdown_local_links_and_anchors_resolve(self) -> None:
        markdown_files = [
            path
            for path in PROJECT_ROOT.rglob("*.md")
            if ".git" not in path.parts and ".venv" not in path.parts
        ]
        failures: list[str] = []

        for source_path in markdown_files:
            content = source_path.read_text(encoding="utf-8")
            for raw_target in re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", content):
                target = raw_target.strip().strip("<>").split(maxsplit=1)[0]
                if target.startswith(("http://", "https://", "mailto:")):
                    continue

                path_part, _, anchor = unquote(target).partition("#")
                target_path = source_path if not path_part else source_path.parent / path_part
                target_path = target_path.resolve()
                try:
                    target_path.relative_to(PROJECT_ROOT)
                except ValueError:
                    failures.append(
                        f"{source_path.relative_to(PROJECT_ROOT)} -> outside repository: {target}"
                    )
                    continue
                if not target_path.exists():
                    failures.append(
                        f"{source_path.relative_to(PROJECT_ROOT)} -> missing: {target}"
                    )
                    continue
                if anchor and target_path.suffix.lower() == ".md":
                    anchors = _markdown_anchors(target_path.read_text(encoding="utf-8"))
                    if anchor.lower() not in anchors:
                        failures.append(
                            f"{source_path.relative_to(PROJECT_ROOT)} -> missing anchor: {target}"
                        )

        self.assertEqual(failures, [])


def _markdown_anchors(content: str) -> set[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", content, flags=re.MULTILINE):
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", heading)
        text = re.sub(r"[`*_~]", "", text).lower().strip()
        slug = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
        slug = re.sub(r"\s+", "-", slug)
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        anchors.add(slug if count == 0 else f"{slug}-{count}")
    return anchors


if __name__ == "__main__":
    unittest.main()
