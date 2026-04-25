from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nagient.app.configuration import WorkspaceConfig
from nagient.app.settings import Settings
from nagient.backups.manager import BackupManager
from nagient.workspace.manager import WorkspaceManager


class BackupManagerTests(unittest.TestCase):
    def test_create_diff_restore_and_prune_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            workspace_root = Path(temp_dir) / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            (workspace_root / "note.txt").write_text("v1", encoding="utf-8")

            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            workspace_manager = WorkspaceManager(settings)
            layout = workspace_manager.ensure_layout(
                WorkspaceConfig(root=workspace_root, mode="bounded")
            )
            backup_manager = BackupManager()

            first = backup_manager.create_snapshot(layout, reason="initial")
            (workspace_root / "note.txt").write_text("v2", encoding="utf-8")
            second = backup_manager.create_snapshot(layout, reason="updated")

            snapshots = backup_manager.list_snapshots(layout)
            self.assertEqual(len(snapshots), 2)

            changes = backup_manager.diff_snapshots(layout, first.snapshot_id, second.snapshot_id)
            self.assertTrue(any(change["path"] == "note.txt" for change in changes))

            backup_manager.restore_snapshot(layout, first.snapshot_id)
            self.assertEqual((workspace_root / "note.txt").read_text(encoding="utf-8"), "v1")

            removed = backup_manager.prune_snapshots(layout, keep=1)
            self.assertEqual(len(removed), 1)


if __name__ == "__main__":
    unittest.main()
