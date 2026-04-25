from __future__ import annotations

import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from nagient.workspace.manager import WorkspaceLayout


@dataclass(frozen=True)
class BackupSnapshot:
    snapshot_id: str
    ref_name: str
    created_at: str
    reason: str
    label: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "snapshot_id": self.snapshot_id,
            "ref_name": self.ref_name,
            "created_at": self.created_at,
            "reason": self.reason,
        }
        if self.label is not None:
            payload["label"] = self.label
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> BackupSnapshot:
        return cls(
            snapshot_id=str(payload.get("snapshot_id", "")),
            ref_name=str(payload.get("ref_name", "")),
            created_at=str(payload.get("created_at", "")),
            reason=str(payload.get("reason", "")),
            label=str(payload["label"]) if "label" in payload else None,
        )


class BackupManager:
    def create_snapshot(
        self,
        layout: WorkspaceLayout,
        *,
        reason: str,
        label: str | None = None,
    ) -> BackupSnapshot:
        repo_dir = self._repo_dir(layout)
        self._ensure_repo(repo_dir)
        self._sync_workspace(layout.root, repo_dir)
        self._git(["add", "-A"], cwd=repo_dir)
        created_at = _utc_now()
        tree_hash = self._git(["write-tree"], cwd=repo_dir).strip()
        commit_message = label or reason
        commit_hash = self._git(
            ["commit-tree", tree_hash, "-m", commit_message],
            cwd=repo_dir,
            env=self._git_env(created_at),
        ).strip()
        ref_name = f"refs/nagient/snapshots/{created_at}-{uuid.uuid4().hex[:8]}"
        self._git(["update-ref", ref_name, commit_hash], cwd=repo_dir)
        snapshot = BackupSnapshot(
            snapshot_id=commit_hash,
            ref_name=ref_name,
            created_at=created_at,
            reason=reason,
            label=label,
        )
        self._write_metadata(layout, snapshot)
        return snapshot

    def list_snapshots(self, layout: WorkspaceLayout) -> list[BackupSnapshot]:
        metadata_dir = self._metadata_dir(layout)
        if not metadata_dir.exists():
            return []
        snapshots: list[BackupSnapshot] = []
        for path in sorted(metadata_dir.glob("*.json"), reverse=True):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                snapshots.append(BackupSnapshot.from_dict(payload))
        return snapshots

    def diff_snapshots(
        self,
        layout: WorkspaceLayout,
        snapshot_id: str,
        other_snapshot_id: str,
    ) -> list[dict[str, str]]:
        repo_dir = self._repo_dir(layout)
        output = self._git(
            ["diff", "--name-status", snapshot_id, other_snapshot_id],
            cwd=repo_dir,
        )
        changes: list[dict[str, str]] = []
        for raw_line in output.splitlines():
            parts = raw_line.split("\t", 1)
            if len(parts) != 2:
                continue
            changes.append({"change_type": parts[0], "path": parts[1]})
        return changes

    def restore_snapshot(self, layout: WorkspaceLayout, snapshot_id: str) -> dict[str, object]:
        repo_dir = self._repo_dir(layout)
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "snapshot.tar"
            export_dir = Path(temp_dir) / "export"
            export_dir.mkdir(parents=True, exist_ok=True)
            self._git(
                ["archive", "--format=tar", snapshot_id, "-o", str(archive_path)],
                cwd=repo_dir,
            )
            with tarfile.open(archive_path) as archive:
                archive.extractall(export_dir)
            self._sync_tree(export_dir, layout.root, preserve={".git"})
        return {
            "restored": True,
            "snapshot_id": snapshot_id,
            "workspace_root": str(layout.root),
        }

    def prune_snapshots(self, layout: WorkspaceLayout, *, keep: int) -> list[str]:
        snapshots = self.list_snapshots(layout)
        removed_refs: list[str] = []
        for snapshot in snapshots[keep:]:
            self._git(["update-ref", "-d", snapshot.ref_name], cwd=self._repo_dir(layout))
            metadata_path = self._metadata_dir(layout) / f"{snapshot.snapshot_id}.json"
            if metadata_path.exists():
                metadata_path.unlink()
            removed_refs.append(snapshot.ref_name)
        if removed_refs:
            self._git(["reflog", "expire", "--expire=now", "--all"], cwd=self._repo_dir(layout))
            self._git(["gc", "--prune=now"], cwd=self._repo_dir(layout))
        return removed_refs

    def export_snapshot(
        self,
        layout: WorkspaceLayout,
        snapshot_id: str,
        output_path: Path,
    ) -> Path:
        repo_dir = self._repo_dir(layout)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.suffix in {".tar", ".gz"} or output_path.name.endswith(".tar.gz"):
            self._git(
                ["archive", "--format=tar", snapshot_id, "-o", str(output_path)],
                cwd=repo_dir,
            )
            return output_path

        output_path.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "snapshot.tar"
            self._git(
                ["archive", "--format=tar", snapshot_id, "-o", str(archive_path)],
                cwd=repo_dir,
            )
            with tarfile.open(archive_path) as archive:
                archive.extractall(output_path)
        return output_path

    def _repo_dir(self, layout: WorkspaceLayout) -> Path:
        return layout.backups_dir / "repo"

    def _metadata_dir(self, layout: WorkspaceLayout) -> Path:
        return layout.backups_dir / "snapshots"

    def _ensure_repo(self, repo_dir: Path) -> None:
        if (repo_dir / ".git").exists():
            return
        repo_dir.mkdir(parents=True, exist_ok=True)
        self._git(["init"], cwd=repo_dir)

    def _write_metadata(self, layout: WorkspaceLayout, snapshot: BackupSnapshot) -> None:
        metadata_dir = self._metadata_dir(layout)
        metadata_dir.mkdir(parents=True, exist_ok=True)
        path = metadata_dir / f"{snapshot.snapshot_id}.json"
        path.write_text(json.dumps(snapshot.to_dict(), indent=2) + "\n", encoding="utf-8")

    def _sync_workspace(self, source_root: Path, repo_dir: Path) -> None:
        self._sync_tree(source_root, repo_dir, preserve={".git"})

    def _sync_tree(
        self,
        source_root: Path,
        target_root: Path,
        *,
        preserve: set[str],
    ) -> None:
        for target_entry in target_root.iterdir():
            if target_entry.name in preserve:
                continue
            source_entry = source_root / target_entry.name
            if not source_entry.exists():
                if target_entry.is_dir():
                    shutil.rmtree(target_entry)
                else:
                    target_entry.unlink()

        for source_entry in source_root.iterdir():
            if source_entry.name in preserve:
                continue
            target_entry = target_root / source_entry.name
            if source_entry.is_dir():
                if target_entry.exists() and not target_entry.is_dir():
                    target_entry.unlink()
                target_entry.mkdir(parents=True, exist_ok=True)
                self._sync_tree(source_entry, target_entry, preserve=preserve)
            else:
                target_entry.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_entry, target_entry)

    def _git(
        self,
        args: list[str],
        *,
        cwd: Path,
        env: dict[str, str] | None = None,
    ) -> str:
        process = subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(process.stderr.strip() or process.stdout.strip())
        return process.stdout

    def _git_env(self, created_at: str) -> dict[str, str]:
        return {
            "PATH": os.environ.get("PATH", ""),
            "GIT_AUTHOR_NAME": "Nagient Backup",
            "GIT_AUTHOR_EMAIL": "nagient@local",
            "GIT_COMMITTER_NAME": "Nagient Backup",
            "GIT_COMMITTER_EMAIL": "nagient@local",
            "GIT_AUTHOR_DATE": created_at,
            "GIT_COMMITTER_DATE": created_at,
        }


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
