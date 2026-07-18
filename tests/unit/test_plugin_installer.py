from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from nagient.plugins.dependencies import (
    PluginDependencyError,
    install_plugin_dependencies,
    manifest_dependencies,
)
from nagient.plugins.installer import (
    PluginInstallError,
    install_plugin,
    list_installed_plugins,
    remove_plugin,
)


class PluginInstallerTests(unittest.TestCase):
    def test_manifest_dependencies_are_normalized(self) -> None:
        dependencies, requirements_file = manifest_dependencies(
            {
                "dependencies": [" aiogram>=3,<4 ", "aiohttp"],
                "requirements_file": "requirements.txt",
            }
        )

        self.assertEqual(dependencies, ["aiogram>=3,<4", "aiohttp"])
        self.assertEqual(requirements_file, "requirements.txt")

    def test_requirements_file_cannot_escape_plugin_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(PluginDependencyError):
                install_plugin_dependencies(
                    Path(temp_dir),
                    [],
                    requirements_file="../requirements.txt",
                )

    def test_install_without_dependencies_records_not_required_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository = root / "repository"
            repository.mkdir()
            (repository / "provider.toml").write_text(
                'type = "provider"\nid = "example.provider"\nversion = "1.2.3"\n',
                encoding="utf-8",
            )
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.com",
                    "commit",
                    "-qm",
                    "initial",
                ],
                check=True,
            )

            installed = install_plugin(
                repository.as_uri(),
                plugins_dir=root / "plugins",
                providers_dir=root / "providers",
                tools_dir=root / "tools",
            )

            self.assertEqual(installed.dependencies["status"], "not_required")
            self.assertFalse((installed.directory / ".venv").exists())

    def test_installs_provider_from_git_repository_and_lists_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository = root / "repository"
            repository.mkdir()
            (repository / "provider.toml").write_text(
                'type = "provider"\nid = "example.provider"\nversion = "1.2.3"\n',
                encoding="utf-8",
            )
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.com",
                    "commit",
                    "-qm",
                    "initial",
                ],
                check=True,
            )
            installed = install_plugin(
                f"provider:{repository.as_uri()}",
                plugins_dir=root / "plugins",
                providers_dir=root / "providers",
                tools_dir=root / "tools",
            )

            self.assertEqual(installed.plugin_id, "example.provider")
            self.assertEqual(installed.version, "1.2.3")
            listed = list_installed_plugins(
                plugins_dir=root / "plugins",
                providers_dir=root / "providers",
                tools_dir=root / "tools",
            )
            self.assertEqual(listed[0]["source"], repository.as_uri())

            removed = remove_plugin(
                "example.provider",
                plugins_dir=root / "plugins",
                providers_dir=root / "providers",
                tools_dir=root / "tools",
            )
            self.assertTrue(removed["removed"])

    def test_rejects_repository_without_a_single_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository = root / "repository"
            repository.mkdir()
            (repository / "README.md").write_text("empty", encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.com",
                    "commit",
                    "-qm",
                    "initial",
                ],
                check=True,
            )

            with self.assertRaises(PluginInstallError):
                install_plugin(
                    repository.as_uri(),
                    plugins_dir=root / "plugins",
                    providers_dir=root / "providers",
                    tools_dir=root / "tools",
                )
