from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nagient.app.configuration import WorkspaceConfig
from nagient.app.settings import Settings
from nagient.workspace.manager import WorkspaceManager


class WorkspaceManagerTests(unittest.TestCase):
    def test_ensure_layout_creates_visible_workspace_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            manager = WorkspaceManager(settings)

            layout = manager.ensure_layout(
                WorkspaceConfig(root=workspace_root, mode="bounded")
            )

            self.assertTrue((workspace_root / ".nagient" / "memory").exists())
            self.assertTrue((workspace_root / ".nagient" / "notes").exists())
            self.assertTrue((workspace_root / ".nagient" / "plans").exists())
            self.assertTrue((workspace_root / ".nagient" / "jobs").exists())
            self.assertTrue((workspace_root / ".nagient" / "scripts").exists())
            self.assertTrue((workspace_root / ".nagient" / "workspace.json").exists())
            self.assertEqual(layout.metadata.mode, "bounded")

    def test_guard_path_blocks_outside_root_in_bounded_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            outside_path = Path(temp_dir) / "outside.txt"
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            manager = WorkspaceManager(settings)
            layout = manager.ensure_layout(
                WorkspaceConfig(root=workspace_root, mode="bounded")
            )

            guarded = manager.guard_path(layout, "notes.txt")
            self.assertEqual(guarded, (workspace_root / "notes.txt").resolve())
            with self.assertRaises(PermissionError):
                manager.guard_path(layout, outside_path)

    def test_unsafe_mode_keeps_secret_paths_protected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            outside_path = Path(temp_dir) / "outside.txt"
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            manager = WorkspaceManager(settings)
            layout = manager.ensure_layout(
                WorkspaceConfig(root=workspace_root, mode="unsafe")
            )

            self.assertEqual(manager.guard_path(layout, outside_path), outside_path.resolve())
            with self.assertRaises(PermissionError):
                manager.guard_path(layout, settings.secrets_file)


if __name__ == "__main__":
    unittest.main()
