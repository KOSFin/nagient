from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

from nagient.app.configuration import WorkspaceConfig
from nagient.app.settings import Settings
from nagient.domain.entities.system_state import CheckIssue
from nagient.domain.entities.workspace import WorkspaceMetadata, WorkspaceState

VISIBLE_WORKSPACE_SUBDIRS = ("memory", "notes", "plans", "jobs", "scripts")


@dataclass(frozen=True)
class WorkspaceLayout:
    settings: Settings
    config: WorkspaceConfig
    metadata: WorkspaceMetadata
    root: Path
    nagient_dir: Path
    memory_dir: Path
    notes_dir: Path
    plans_dir: Path
    jobs_dir: Path
    scripts_dir: Path
    state_dir: Path
    backups_dir: Path
    protected_paths: tuple[Path, ...]


class WorkspaceManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def inspect(self, workspace: WorkspaceConfig) -> WorkspaceState:
        issues: list[CheckIssue] = []
        root = workspace.root.resolve()
        nagient_dir = root / ".nagient"
        workspace_id = _workspace_id(root)
        if root.exists() and not root.is_dir():
            issues.append(
                CheckIssue(
                    severity="error",
                    code="workspace.invalid_root",
                    message=f"Workspace root {str(root)!r} is not a directory.",
                    source="workspace",
                )
            )
        if workspace.mode == "unsafe":
            issues.append(
                CheckIssue(
                    severity="warning",
                    code="workspace.unsafe_mode",
                    message=(
                        "Workspace is running in unsafe mode; path guards are relaxed, "
                        "but protected secret stores remain blocked."
                    ),
                    source="workspace",
                )
            )

        status = "ready"
        if any(issue.severity == "error" for issue in issues):
            status = "failed"
        elif issues:
            status = "degraded"

        return WorkspaceState(
            workspace_id=workspace_id,
            root=str(root),
            mode=workspace.mode,
            nagient_dir=str(nagient_dir),
            status=status,
            backup_enabled=True,
            issues=issues,
        )

    def ensure_layout(self, workspace: WorkspaceConfig) -> WorkspaceLayout:
        root = workspace.root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        nagient_dir = root / ".nagient"
        nagient_dir.mkdir(parents=True, exist_ok=True)
        for name in VISIBLE_WORKSPACE_SUBDIRS:
            (nagient_dir / name).mkdir(parents=True, exist_ok=True)

        workspace_id = _workspace_id(root)
        workspace_state_dir = self._settings.state_dir / "workspaces" / workspace_id
        workspace_state_dir.mkdir(parents=True, exist_ok=True)
        backups_dir = self._settings.state_dir / "backups" / workspace_id
        backups_dir.mkdir(parents=True, exist_ok=True)

        metadata_path = nagient_dir / "workspace.json"
        state_metadata_path = workspace_state_dir / "workspace.json"
        current_time = _utc_now()
        if metadata_path.exists():
            metadata = WorkspaceMetadata.from_dict(
                json.loads(metadata_path.read_text(encoding="utf-8"))
            )
            created_at = metadata.created_at
        else:
            created_at = current_time

        metadata = WorkspaceMetadata(
            workspace_id=workspace_id,
            root=str(root),
            mode=workspace.mode,
            nagient_dir=str(nagient_dir),
            created_at=created_at,
            updated_at=current_time,
            policy={
                "mode": workspace.mode,
                "visible_dirs": list(VISIBLE_WORKSPACE_SUBDIRS),
                "protected_paths": [
                    str(path) for path in self._protected_paths(root)
                ],
            },
        )
        payload = json.dumps(metadata.to_dict(), indent=2) + "\n"
        metadata_path.write_text(payload, encoding="utf-8")
        state_metadata_path.write_text(payload, encoding="utf-8")

        return WorkspaceLayout(
            settings=self._settings,
            config=workspace,
            metadata=metadata,
            root=root,
            nagient_dir=nagient_dir,
            memory_dir=nagient_dir / "memory",
            notes_dir=nagient_dir / "notes",
            plans_dir=nagient_dir / "plans",
            jobs_dir=nagient_dir / "jobs",
            scripts_dir=nagient_dir / "scripts",
            state_dir=workspace_state_dir,
            backups_dir=backups_dir,
            protected_paths=self._protected_paths(root),
        )

    def guard_path(
        self,
        layout: WorkspaceLayout,
        candidate: str | Path,
    ) -> Path:
        path = Path(candidate).expanduser()
        if not path.is_absolute():
            path = (layout.root / path).resolve()
        else:
            path = path.resolve()

        for protected_path in layout.protected_paths:
            if _is_relative_to(path, protected_path):
                msg = f"Path {str(path)!r} is protected by the Nagient secret policy."
                raise PermissionError(msg)

        if layout.config.mode != "unsafe" and not _is_relative_to(path, layout.root):
            msg = f"Path {str(path)!r} is outside the bounded workspace root."
            raise PermissionError(msg)
        return path

    def resolve_workdir(
        self,
        layout: WorkspaceLayout,
        candidate: str | Path | None = None,
    ) -> Path:
        if candidate is None:
            return layout.root
        return self.guard_path(layout, candidate)

    def is_git_workspace(self, layout: WorkspaceLayout) -> bool:
        return (layout.root / ".git").exists()

    def _protected_paths(self, workspace_root: Path) -> tuple[Path, ...]:
        protected = [
            self._settings.secrets_file.resolve(),
            self._settings.tool_secrets_file.resolve(),
            self._settings.credentials_dir.resolve(),
            (self._settings.state_dir / "auth-sessions").resolve(),
            (self._settings.state_dir / "secrets").resolve(),
        ]
        if _is_relative_to(self._settings.home_dir.resolve(), workspace_root):
            protected.append(self._settings.home_dir.resolve())
        return tuple(protected)


def _workspace_id(root: Path) -> str:
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()
    return digest[:16]


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _is_relative_to(candidate: Path, base: Path) -> bool:
    try:
        candidate.relative_to(base)
    except ValueError:
        return False
    return True
