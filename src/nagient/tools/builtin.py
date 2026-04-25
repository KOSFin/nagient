from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from nagient.domain.entities.system_state import CheckIssue
from nagient.domain.entities.security import InteractionRequest, PostSubmitAction
from nagient.domain.entities.tooling import ToolFunctionManifest, ToolPluginManifest
from nagient.tools.base import (
    BaseToolPlugin,
    LoadedToolPlugin,
    ToolExecutionContext,
    ToolRiskDecision,
)
from nagient.version import __version__


class ResponseReader(Protocol):
    def read(self) -> bytes: ...


class ResponseContextManager(Protocol):
    def __enter__(self) -> ResponseReader: ...

    def __exit__(self, exc_type: object, exc: object, tb: object) -> object: ...


class UrlopenLike(Protocol):
    def __call__(
        self,
        request: Request,
        timeout: float = ...,
    ) -> ResponseContextManager: ...


def _default_urlopen(request: Request, timeout: float = 15.0) -> ResponseContextManager:
    return cast(ResponseContextManager, urlopen(request, timeout=timeout))


class WorkspaceFsToolPlugin(BaseToolPlugin):
    manifest = ToolPluginManifest(
        plugin_id="workspace.fs",
        display_name="Workspace Filesystem",
        version=__version__,
        namespace="workspace.fs",
        entrypoint="<builtin>",
        capabilities=["workspace", "filesystem"],
        functions=[
            ToolFunctionManifest(
                function_name="workspace.fs.list_dir",
                binding="list_dir",
                description="List files and directories under a workspace path.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                permissions=["workspace.read"],
            ),
            ToolFunctionManifest(
                function_name="workspace.fs.read_text",
                binding="read_text",
                description="Read a UTF-8 text file from the workspace.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                permissions=["workspace.read"],
            ),
            ToolFunctionManifest(
                function_name="workspace.fs.write_text",
                binding="write_text",
                description="Write UTF-8 text to a workspace file.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                permissions=["workspace.write"],
                side_effect="write",
                dry_run_supported=True,
            ),
            ToolFunctionManifest(
                function_name="workspace.fs.delete",
                binding="delete_path",
                description="Delete a file or directory inside the workspace.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                permissions=["workspace.delete"],
                side_effect="destructive",
                approval_policy="required",
                dry_run_supported=True,
            ),
        ],
    )

    def list_dir(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        candidate = str(arguments.get("path", "."))
        path = context.workspace_manager.guard_path(context.workspace, candidate)
        entries = []
        for entry in sorted(path.iterdir()):
            entries.append(
                {
                    "name": entry.name,
                    "path": str(entry.relative_to(context.workspace.root)),
                    "kind": "dir" if entry.is_dir() else "file",
                }
            )
        return {"path": str(path), "entries": entries}

    def read_text(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        candidate = arguments.get("path")
        if not isinstance(candidate, str) or not candidate:
            raise ValueError("workspace.fs.read_text requires a string path.")
        path = context.workspace_manager.guard_path(context.workspace, candidate)
        max_bytes = arguments.get("max_bytes", 20000)
        if not isinstance(max_bytes, int) or max_bytes <= 0:
            max_bytes = 20000
        payload = path.read_bytes()
        truncated = len(payload) > max_bytes
        return {
            "path": str(path),
            "content": payload[:max_bytes].decode("utf-8", errors="replace"),
            "truncated": truncated,
        }

    def write_text(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        candidate = arguments.get("path")
        content = arguments.get("content")
        if not isinstance(candidate, str) or not candidate:
            raise ValueError("workspace.fs.write_text requires a string path.")
        if not isinstance(content, str):
            raise ValueError("workspace.fs.write_text requires string content.")
        path = context.workspace_manager.guard_path(context.workspace, candidate)
        append = bool(arguments.get("append", False))
        if context.dry_run:
            return {
                "path": str(path),
                "append": append,
                "written": False,
                "dry_run": True,
            }
        path.parent.mkdir(parents=True, exist_ok=True)
        if append:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(content)
        else:
            path.write_text(content, encoding="utf-8")
        return {
            "path": str(path),
            "append": append,
            "written": True,
            "bytes": len(content.encode("utf-8")),
        }

    def delete_path(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        candidate = arguments.get("path")
        if not isinstance(candidate, str) or not candidate:
            raise ValueError("workspace.fs.delete requires a string path.")
        path = context.workspace_manager.guard_path(context.workspace, candidate)
        if context.dry_run:
            return {"path": str(path), "deleted": False, "dry_run": True}
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
        return {"path": str(path), "deleted": True}


class WorkspaceShellToolPlugin(BaseToolPlugin):
    manifest = ToolPluginManifest(
        plugin_id="workspace.shell",
        display_name="Workspace Shell",
        version=__version__,
        namespace="workspace.shell",
        entrypoint="<builtin>",
        capabilities=["workspace", "shell"],
        functions=[
            ToolFunctionManifest(
                function_name="workspace.shell.run",
                binding="run",
                description="Run a shell command with workspace-aware policy guards.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                permissions=["workspace.shell"],
                side_effect="write",
                approval_policy="policy",
                dry_run_supported=True,
            )
        ],
    )

    def assess_risk(
        self,
        function_name: str,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> ToolRiskDecision:
        del function_name
        command = str(arguments.get("command", ""))
        for protected_path in context.workspace.protected_paths:
            if str(protected_path) in command:
                return ToolRiskDecision(
                    approval_policy="required",
                    reason="Command references a protected Nagient path.",
                )
        dangerous_markers = [
            " rm ",
            "rm -",
            "git reset",
            "git restore",
            "git checkout --",
            "sudo ",
            "chmod ",
            "chown ",
            " dd ",
            "mkfs",
        ]
        normalized = f" {command.strip()} "
        if any(marker in normalized for marker in dangerous_markers):
            return ToolRiskDecision(
                approval_policy="required",
                reason="Command matches a high-risk shell policy.",
            )
        if bool(arguments.get("read_only", False)):
            return ToolRiskDecision(
                approval_policy="never",
                checkpoint_required=False,
            )
        return ToolRiskDecision(approval_policy="inherit", checkpoint_required=True)

    def run(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        command = arguments.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValueError("workspace.shell.run requires a non-empty command string.")
        workdir = context.workspace_manager.resolve_workdir(
            context.workspace,
            arguments.get("cwd"),
        )
        timeout_seconds = arguments.get("timeout_seconds", 30)
        if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
            timeout_seconds = 30
        if context.dry_run:
            return {
                "command": command,
                "cwd": str(workdir),
                "dry_run": True,
            }
        process = subprocess.run(
            command,
            cwd=workdir,
            shell=True,
            executable="/bin/sh",
            env=_shell_env(context.workspace.root),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "command": command,
            "cwd": str(workdir),
            "exit_code": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
        }


class WorkspaceGitToolPlugin(BaseToolPlugin):
    manifest = ToolPluginManifest(
        plugin_id="workspace.git",
        display_name="Workspace Git",
        version=__version__,
        namespace="workspace.git",
        entrypoint="<builtin>",
        capabilities=["workspace", "git"],
        functions=[
            ToolFunctionManifest(
                function_name="workspace.git.status",
                binding="status",
                description="Show git status for the workspace repository.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                permissions=["workspace.git.read"],
            ),
            ToolFunctionManifest(
                function_name="workspace.git.diff",
                binding="diff",
                description="Show git diff output for the workspace repository.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                permissions=["workspace.git.read"],
            ),
            ToolFunctionManifest(
                function_name="workspace.git.restore_path",
                binding="restore_path",
                description="Restore a file in the workspace repository from HEAD.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                permissions=["workspace.git.write"],
                side_effect="destructive",
                approval_policy="required",
                dry_run_supported=True,
            ),
        ],
    )

    def status(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        del arguments
        if not context.workspace_manager.is_git_workspace(context.workspace):
            return {"git_repository": False, "status": ""}
        output = _run_git(["status", "--short"], cwd=context.workspace.root)
        return {"git_repository": True, "status": output}

    def diff(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        if not context.workspace_manager.is_git_workspace(context.workspace):
            return {"git_repository": False, "diff": ""}
        revision = arguments.get("revision")
        args = ["diff"]
        if isinstance(revision, str) and revision:
            args.append(revision)
        output = _run_git(args, cwd=context.workspace.root)
        return {"git_repository": True, "diff": output}

    def restore_path(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        candidate = arguments.get("path")
        if not isinstance(candidate, str) or not candidate:
            raise ValueError("workspace.git.restore_path requires a string path.")
        path = context.workspace_manager.guard_path(context.workspace, candidate)
        if context.dry_run:
            return {"path": str(path), "restored": False, "dry_run": True}
        if not context.workspace_manager.is_git_workspace(context.workspace):
            raise ValueError("The current workspace is not a git repository.")
        relative = str(path.relative_to(context.workspace.root))
        _run_git(
            ["restore", "--worktree", "--source=HEAD", "--", relative],
            cwd=context.workspace.root,
        )
        return {"path": relative, "restored": True}


class TransportInteractionToolPlugin(BaseToolPlugin):
    manifest = ToolPluginManifest(
        plugin_id="transport.interaction",
        display_name="Transport Interaction",
        version=__version__,
        namespace="transport.interaction",
        entrypoint="<builtin>",
        capabilities=["interaction"],
        functions=[
            ToolFunctionManifest(
                function_name="transport.interaction.request",
                binding="request",
                description="Create a secure user interaction request.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                permissions=["transport.interaction"],
                side_effect="system",
            )
        ],
    )

    def assess_risk(
        self,
        function_name: str,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> ToolRiskDecision:
        del function_name, arguments, context
        return ToolRiskDecision(approval_policy="inherit", checkpoint_required=False)

    def request(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        prompt = arguments.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("transport.interaction.request requires a non-empty prompt.")
        interaction_type = str(arguments.get("interaction_type", "secret_input"))
        actions = arguments.get("post_submit_actions", [])
        if not isinstance(actions, list):
            raise ValueError("post_submit_actions must be a list of action payloads.")
        interaction = InteractionRequest(
            request_id=str(arguments.get("request_id", "")),
            session_id=context.session_id or "system",
            transport_id=context.transport_id or "console",
            interaction_type=interaction_type,
            prompt=prompt,
            status="pending",
            created_at=_utc_now(),
            post_submit_actions=[
                PostSubmitAction.from_dict(item) for item in actions if isinstance(item, dict)
            ],
            metadata=dict(arguments.get("metadata", {}))
            if isinstance(arguments.get("metadata"), dict)
            else {},
        )
        stored = context.request_interaction(interaction)
        return {
            "request_id": stored.request_id,
            "status": stored.status,
            "transport_id": stored.transport_id,
        }


class SystemBackupToolPlugin(BaseToolPlugin):
    manifest = ToolPluginManifest(
        plugin_id="system.backup",
        display_name="System Backup",
        version=__version__,
        namespace="system.backup",
        entrypoint="<builtin>",
        capabilities=["backup"],
        functions=[
            ToolFunctionManifest(
                function_name="system.backup.create",
                binding="create_snapshot",
                description="Create a local workspace snapshot.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                permissions=["system.backup"],
                side_effect="system",
            ),
            ToolFunctionManifest(
                function_name="system.backup.list",
                binding="list_snapshots",
                description="List local backup snapshots.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                permissions=["system.backup"],
            ),
            ToolFunctionManifest(
                function_name="system.backup.diff",
                binding="diff_snapshots",
                description="Diff two local backup snapshots.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                permissions=["system.backup"],
            ),
            ToolFunctionManifest(
                function_name="system.backup.restore",
                binding="restore_snapshot",
                description="Restore a local backup snapshot into the workspace.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                permissions=["system.backup.restore"],
                side_effect="destructive",
                approval_policy="required",
            ),
            ToolFunctionManifest(
                function_name="system.backup.prune",
                binding="prune_snapshots",
                description="Prune older backup snapshots.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                permissions=["system.backup.prune"],
                side_effect="system",
            ),
            ToolFunctionManifest(
                function_name="system.backup.export",
                binding="export_snapshot",
                description="Export a backup snapshot to a file or directory.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                permissions=["system.backup.export"],
            ),
        ],
    )

    def assess_risk(
        self,
        function_name: str,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> ToolRiskDecision:
        del arguments, context
        if function_name == "system.backup.restore":
            return ToolRiskDecision(approval_policy="inherit", checkpoint_required=True)
        return ToolRiskDecision(approval_policy="inherit", checkpoint_required=False)

    def create_snapshot(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        snapshot = context.backup_manager.create_snapshot(
            context.workspace,
            reason=str(arguments.get("reason", "manual backup")),
            label=str(arguments["label"]) if "label" in arguments else None,
        )
        return snapshot.to_dict()

    def list_snapshots(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        del arguments
        snapshots = context.backup_manager.list_snapshots(context.workspace)
        return {"snapshots": [snapshot.to_dict() for snapshot in snapshots]}

    def diff_snapshots(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        snapshot_id = arguments.get("snapshot_id")
        other_snapshot_id = arguments.get("other_snapshot_id")
        if not isinstance(snapshot_id, str) or not isinstance(other_snapshot_id, str):
            raise ValueError("system.backup.diff requires snapshot_id and other_snapshot_id.")
        changes = context.backup_manager.diff_snapshots(
            context.workspace,
            snapshot_id,
            other_snapshot_id,
        )
        return {"changes": changes}

    def restore_snapshot(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        snapshot_id = arguments.get("snapshot_id")
        if not isinstance(snapshot_id, str) or not snapshot_id:
            raise ValueError("system.backup.restore requires snapshot_id.")
        return context.backup_manager.restore_snapshot(context.workspace, snapshot_id)

    def prune_snapshots(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        keep = arguments.get("keep", 10)
        if not isinstance(keep, int) or keep <= 0:
            raise ValueError("system.backup.prune requires a positive keep value.")
        removed = context.backup_manager.prune_snapshots(context.workspace, keep=keep)
        return {"removed_refs": removed}

    def export_snapshot(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        snapshot_id = arguments.get("snapshot_id")
        output_path = arguments.get("output_path")
        if not isinstance(snapshot_id, str) or not snapshot_id:
            raise ValueError("system.backup.export requires snapshot_id.")
        if not isinstance(output_path, str) or not output_path:
            raise ValueError("system.backup.export requires output_path.")
        path = Path(output_path).expanduser().resolve()
        exported = context.backup_manager.export_snapshot(context.workspace, snapshot_id, path)
        return {"exported_to": str(exported)}


class SystemReconcileToolPlugin(BaseToolPlugin):
    manifest = ToolPluginManifest(
        plugin_id="system.reconcile",
        display_name="System Reconcile",
        version=__version__,
        namespace="system.reconcile",
        entrypoint="<builtin>",
        capabilities=["system"],
        functions=[
            ToolFunctionManifest(
                function_name="system.reconcile.run",
                binding="run_reconcile",
                description="Run the Nagient reconcile cycle and return the activation report.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                permissions=["system.reconcile"],
                side_effect="system",
            )
        ],
    )

    def assess_risk(
        self,
        function_name: str,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> ToolRiskDecision:
        del function_name, arguments, context
        return ToolRiskDecision(approval_policy="inherit", checkpoint_required=False)

    def run_reconcile(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        del arguments
        return context.invoke_reconcile()


@dataclass(frozen=True)
class GitHubApiToolPlugin(BaseToolPlugin):
    opener: UrlopenLike = _default_urlopen
    manifest: ToolPluginManifest = field(
        default_factory=lambda: ToolPluginManifest(
            plugin_id="github.api",
            display_name="GitHub API",
            version=__version__,
            namespace="github.api",
            entrypoint="<builtin>",
            capabilities=["github"],
            optional_config=["token_secret", "base_url", "timeout_seconds"],
            functions=[
                ToolFunctionManifest(
                    function_name="github.api.get_repository",
                    binding="get_repository",
                    description="Fetch repository metadata from the GitHub API.",
                    input_schema={"type": "object"},
                    output_schema={"type": "object"},
                    permissions=["github.read"],
                    secret_bindings=["token_secret"],
                )
            ],
        )
    )

    def validate_config(
        self,
        tool_id: str,
        config: Mapping[str, object],
        secret_broker: object,
    ) -> list[CheckIssue]:
        issues: list[CheckIssue] = []
        token_secret = config.get("token_secret")
        if token_secret is not None and not isinstance(token_secret, str):
            issues.append(
                CheckIssue(
                    severity="error",
                    code="tool.github.invalid_token_secret",
                    message="github.api token_secret must be a string when provided.",
                    source=tool_id,
                )
            )
        has_secret = getattr(secret_broker, "has_secret", None)
        if isinstance(token_secret, str) and callable(has_secret):
            if not has_secret(token_secret, scope_hint="tool"):
                issues.append(
                    CheckIssue(
                        severity="warning",
                        code="tool.github.missing_secret",
                        message=(
                            f"Tool {tool_id!r} references missing GitHub secret "
                            f"{token_secret!r}."
                        ),
                        source=tool_id,
                    )
                )
        return issues

    def get_repository(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        owner = arguments.get("owner")
        repo = arguments.get("repo")
        if not isinstance(owner, str) or not owner:
            raise ValueError("github.api.get_repository requires owner.")
        if not isinstance(repo, str) or not repo:
            raise ValueError("github.api.get_repository requires repo.")

        base_url = context.config.get("base_url", "https://api.github.com")
        if not isinstance(base_url, str) or not base_url:
            base_url = "https://api.github.com"
        token_secret = context.config.get("token_secret", "GITHUB_TOKEN")
        if not isinstance(token_secret, str) or not token_secret:
            token_secret = "GITHUB_TOKEN"
        if context.dry_run:
            return {"url": f"{base_url.rstrip('/')}/repos/{owner}/{repo}", "dry_run": True}

        token = context.secret_broker.resolve_secret(token_secret, scope_hint="tool")
        request = Request(
            f"{base_url.rstrip('/')}/repos/{owner}/{repo}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "nagient",
            },
            method="GET",
        )
        timeout_seconds = context.config.get("timeout_seconds", 15)
        if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
            timeout_seconds = 15
        try:
            with self.opener(request, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:400]
            raise ValueError(f"GitHub API returned HTTP {exc.code}: {body}") from exc
        except URLError as exc:
            raise ValueError(f"GitHub API request failed: {exc.reason}") from exc
        if not isinstance(payload, dict):
            raise ValueError("GitHub API returned an unexpected payload.")
        return {
            "full_name": payload.get("full_name"),
            "private": payload.get("private"),
            "default_branch": payload.get("default_branch"),
            "description": payload.get("description"),
            "html_url": payload.get("html_url"),
        }


def builtin_tools() -> list[LoadedToolPlugin]:
    plugins: list[BaseToolPlugin] = [
        WorkspaceFsToolPlugin(),
        WorkspaceShellToolPlugin(),
        WorkspaceGitToolPlugin(),
        TransportInteractionToolPlugin(),
        SystemBackupToolPlugin(),
        SystemReconcileToolPlugin(),
        GitHubApiToolPlugin(),
    ]
    return [
        LoadedToolPlugin(
            manifest=plugin.manifest,
            implementation=plugin,
            source="<builtin>",
        )
        for plugin in plugins
    ]


def _shell_env(workspace_root: Path) -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(workspace_root),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def _run_git(args: list[str], *, cwd: Path) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=_shell_env(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        raise ValueError(process.stderr.strip() or process.stdout.strip())
    return process.stdout


def _utc_now() -> str:
    from time import gmtime, strftime

    return strftime("%Y-%m-%dT%H:%M:%SZ", gmtime())
