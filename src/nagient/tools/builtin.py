from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from nagient.domain.entities.config_fields import ConfigFieldSpec
from nagient.domain.entities.security import InteractionRequest, PostSubmitAction
from nagient.domain.entities.system_state import CheckIssue
from nagient.domain.entities.tooling import ToolFunctionManifest, ToolPluginManifest
from nagient.tools.agent_builtin import (
    AgentMemoryToolPlugin,
    SystemConfigToolPlugin,
    SystemJobsToolPlugin,
    TransportRouterToolPlugin,
)
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


@dataclass(frozen=True)
class _ShellCommandPlan:
    effective_command: str
    notes: list[str] = field(default_factory=list)
    blocked_reason: str | None = None


@dataclass(frozen=True)
class _ShellProcessResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool


_DEFAULT_SHELL_TIMEOUT_SECONDS = 15
_DEFAULT_SHELL_GRACE_SECONDS = 2
_DEFAULT_SHELL_MAX_OUTPUT_CHARS = 8000
_DEFAULT_SHELL_PING_COUNT = 4
_SHELL_BLOCKED_PREFIXES = (
    "watch",
    "top",
    "htop",
    "less",
    "more",
    "man",
    "vim",
    "vi",
    "nano",
    "emacs",
    "yes",
)


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
        optional_config=[
            "timeout_seconds",
            "grace_period_seconds",
            "max_output_chars",
            "default_ping_count",
            "normalize_infinite_commands",
            "enforce_finite_commands",
        ],
        functions=[
            ToolFunctionManifest(
                function_name="workspace.shell.run",
                binding="run",
                description="Run a shell command with workspace-aware policy guards.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "cwd": {"type": "string"},
                        "timeout_seconds": {"type": "integer", "minimum": 1},
                        "max_output_chars": {"type": "integer", "minimum": 1},
                        "read_only": {"type": "boolean"},
                    },
                    "required": ["command"],
                    "additionalProperties": True,
                },
                output_schema={"type": "object"},
                permissions=["workspace.shell"],
                side_effect="write",
                approval_policy="policy",
                dry_run_supported=True,
            )
        ],
    )

    def validate_config(
        self,
        tool_id: str,
        config: Mapping[str, object],
        secret_broker: object,
    ) -> list[CheckIssue]:
        del secret_broker
        issues: list[CheckIssue] = []
        for key in (
            "timeout_seconds",
            "grace_period_seconds",
            "max_output_chars",
            "default_ping_count",
        ):
            value = config.get(key)
            if value is not None and (not isinstance(value, int) or value <= 0):
                issues.append(
                    CheckIssue(
                        severity="error",
                        code="tool.workspace_shell.invalid_config",
                        message=(
                            f"Tool {tool_id!r} must use a positive integer for {key!r}."
                        ),
                        source=tool_id,
                    )
                )
        for key in ("normalize_infinite_commands", "enforce_finite_commands"):
            value = config.get(key)
            if value is not None and not isinstance(value, bool):
                issues.append(
                    CheckIssue(
                        severity="error",
                        code="tool.workspace_shell.invalid_config",
                        message=f"Tool {tool_id!r} must use a boolean for {key!r}.",
                        source=tool_id,
                    )
                )
        return issues

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
        cwd = arguments.get("cwd")
        if cwd is not None and not isinstance(cwd, (str, Path)):
            raise ValueError("workspace.shell.run cwd must be a string path when provided.")
        workdir = context.workspace_manager.resolve_workdir(
            context.workspace,
            cwd,
        )
        timeout_seconds = _positive_int(
            arguments.get("timeout_seconds"),
            default=_positive_int(
                context.config.get("timeout_seconds"),
                default=_DEFAULT_SHELL_TIMEOUT_SECONDS,
            ),
        )
        grace_period_seconds = _positive_int(
            context.config.get("grace_period_seconds"),
            default=_DEFAULT_SHELL_GRACE_SECONDS,
        )
        max_output_chars = _positive_int(
            arguments.get("max_output_chars"),
            default=_positive_int(
                context.config.get("max_output_chars"),
                default=_DEFAULT_SHELL_MAX_OUTPUT_CHARS,
            ),
        )
        default_ping_count = _positive_int(
            context.config.get("default_ping_count"),
            default=_DEFAULT_SHELL_PING_COUNT,
        )
        normalize_infinite_commands = _bool_config(
            context.config.get("normalize_infinite_commands"),
            default=True,
        )
        enforce_finite_commands = _bool_config(
            context.config.get("enforce_finite_commands"),
            default=True,
        )
        command_plan = _plan_shell_command(
            command,
            timeout_seconds=timeout_seconds,
            default_ping_count=default_ping_count,
            normalize_infinite_commands=normalize_infinite_commands,
            enforce_finite_commands=enforce_finite_commands,
        )
        if context.dry_run:
            return {
                "command": command,
                "effective_command": command_plan.effective_command,
                "cwd": str(workdir),
                "notes": command_plan.notes,
                "blocked": command_plan.blocked_reason is not None,
                "blocked_reason": command_plan.blocked_reason,
                "dry_run": True,
            }
        if command_plan.blocked_reason is not None:
            return {
                "command": command,
                "effective_command": command_plan.effective_command,
                "cwd": str(workdir),
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
                "timeout_seconds": timeout_seconds,
                "blocked": True,
                "blocked_reason": command_plan.blocked_reason,
                "notes": command_plan.notes,
                "stdout_truncated": False,
                "stderr_truncated": False,
            }
        process = _run_shell_command(
            command_plan.effective_command,
            cwd=workdir,
            env=_shell_env(context.workspace.root),
            timeout_seconds=timeout_seconds,
            grace_period_seconds=grace_period_seconds,
        )
        stdout, stdout_truncated = _truncate_text(process.stdout, max_output_chars)
        stderr, stderr_truncated = _truncate_text(process.stderr, max_output_chars)
        notes = list(command_plan.notes)
        if stdout_truncated:
            notes.append(
                f"stdout was truncated to {max_output_chars} characters."
            )
        if stderr_truncated:
            notes.append(
                f"stderr was truncated to {max_output_chars} characters."
            )
        if process.timed_out:
            notes.append(
                f"Command reached the runtime timeout after {timeout_seconds} seconds."
            )
        return {
            "command": command,
            "effective_command": command_plan.effective_command,
            "cwd": str(workdir),
            "exit_code": process.exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": process.timed_out,
            "timeout_seconds": timeout_seconds,
            "blocked": False,
            "blocked_reason": None,
            "notes": notes,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }


class WorkspaceGitToolPlugin(BaseToolPlugin):
    manifest = ToolPluginManifest(
        plugin_id="workspace.git",
        display_name="Workspace Git",
        version=__version__,
        namespace="workspace.git",
        entrypoint="<builtin>",
        capabilities=["workspace", "git"],
        optional_config=[
            "author_name",
            "author_email",
            "committer_name",
            "committer_email",
            "username",
            "token_secret",
            "password_secret",
        ],
        config_fields=[
            ConfigFieldSpec(
                key="author_name",
                label="Author name",
                help_text="Git author name used for git operations executed through the agent.",
                value_type="string",
                category="connection",
            ),
            ConfigFieldSpec(
                key="author_email",
                label="Author email",
                help_text="Git author email used for git operations executed through the agent.",
                value_type="string",
                category="connection",
            ),
            ConfigFieldSpec(
                key="committer_name",
                label="Committer name",
                help_text=(
                    "Optional git committer name. When omitted, the author name is reused."
                ),
                value_type="string",
                category="connection",
            ),
            ConfigFieldSpec(
                key="committer_email",
                label="Committer email",
                help_text=(
                    "Optional git committer email. When omitted, the author email is reused."
                ),
                value_type="string",
                category="connection",
            ),
            ConfigFieldSpec(
                key="username",
                label="Git username",
                help_text=(
                    "HTTPS username used when git asks for credentials. Often required together "
                    "with a token or password secret."
                ),
                value_type="string",
                category="connection",
            ),
            ConfigFieldSpec(
                key="token_secret",
                label="Token secret",
                help_text=(
                    "Tool secret name that stores an HTTPS git access token. Takes precedence "
                    "over password_secret when both are configured. You can paste the raw "
                    "token and Nagient will store it for you."
                ),
                value_type="secret",
                category="connection",
                secret=True,
            ),
            ConfigFieldSpec(
                key="password_secret",
                label="Password secret",
                help_text=(
                    "Tool secret name that stores an HTTPS git password when no token is used."
                ),
                value_type="secret",
                category="connection",
                secret=True,
            ),
        ],
        functions=[
            ToolFunctionManifest(
                function_name="workspace.git.run",
                binding="run_command",
                description=(
                    "Run a git subcommand in the workspace repository using the configured "
                    "git identity and credentials."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                        }
                    },
                    "required": ["args"],
                    "additionalProperties": False,
                },
                output_schema={"type": "object"},
                permissions=["workspace.git.read", "workspace.git.write"],
                side_effect="write",
                approval_policy="policy",
                dry_run_supported=True,
            ),
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

    def assess_risk(
        self,
        function_name: str,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> ToolRiskDecision:
        del context
        if function_name != "workspace.git.run":
            return ToolRiskDecision(approval_policy="inherit")
        raw_args = arguments.get("args")
        if not isinstance(raw_args, list) or not raw_args:
            return ToolRiskDecision(approval_policy="required")
        args = [item for item in raw_args if isinstance(item, str) and item.strip()]
        if not args:
            return ToolRiskDecision(approval_policy="required")
        subcommand = args[0].strip().lower()
        if subcommand in {"status", "diff", "log", "show", "rev-parse", "ls-files"}:
            return ToolRiskDecision(
                approval_policy="never",
                checkpoint_required=False,
            )
        return ToolRiskDecision(
            approval_policy="required",
            reason=(
                "This git subcommand can modify repository state, refs, or remote state and "
                "requires approval."
            ),
            checkpoint_required=False,
        )

    def validate_config(
        self,
        tool_id: str,
        config: Mapping[str, object],
        secret_broker: object,
    ) -> list[CheckIssue]:
        issues: list[CheckIssue] = []
        for key in (
            "author_name",
            "author_email",
            "committer_name",
            "committer_email",
            "username",
            "token_secret",
            "password_secret",
        ):
            value = config.get(key)
            if value is not None and not isinstance(value, str):
                issues.append(
                    CheckIssue(
                        severity="error",
                        code="tool.workspace_git.invalid_config",
                        message=f"Tool {tool_id!r} must use a string for {key!r}.",
                        source=tool_id,
                    )
                )
        author_name = _string_config(config, "author_name")
        author_email = _string_config(config, "author_email")
        committer_name = _string_config(config, "committer_name")
        committer_email = _string_config(config, "committer_email")
        username = _string_config(config, "username")
        token_secret = _string_config(config, "token_secret")
        password_secret = _string_config(config, "password_secret")
        if bool(author_name) != bool(author_email):
            issues.append(
                CheckIssue(
                    severity="warning",
                    code="tool.workspace_git.partial_author_identity",
                    message=(
                        f"Tool {tool_id!r} should define both author_name and author_email "
                        "together for a complete git identity."
                    ),
                    source=tool_id,
                )
            )
        if bool(committer_name) != bool(committer_email):
            issues.append(
                CheckIssue(
                    severity="warning",
                    code="tool.workspace_git.partial_committer_identity",
                    message=(
                        f"Tool {tool_id!r} should define both committer_name and "
                        "committer_email together for a complete git identity."
                    ),
                    source=tool_id,
                )
            )
        if (token_secret or password_secret) and not username:
            issues.append(
                CheckIssue(
                    severity="warning",
                    code="tool.workspace_git.missing_username",
                    message=(
                        f"Tool {tool_id!r} should define username when token_secret or "
                        "password_secret is configured for HTTPS git auth."
                    ),
                    source=tool_id,
                )
            )
        if token_secret and password_secret:
            issues.append(
                CheckIssue(
                    severity="warning",
                    code="tool.workspace_git.duplicate_secret",
                    message=(
                        f"Tool {tool_id!r} defines both token_secret and password_secret. "
                        "token_secret will be used first."
                    ),
                    source=tool_id,
                )
            )
        has_secret = getattr(secret_broker, "has_secret", None)
        if callable(has_secret):
            for secret_name in [token_secret, password_secret]:
                if secret_name and not has_secret(secret_name, scope_hint="tool"):
                    issues.append(
                        CheckIssue(
                            severity="error",
                            code="tool.workspace_git.missing_secret",
                            message=(
                                f"Tool {tool_id!r} references missing git secret "
                                f"{secret_name!r}."
                            ),
                            source=tool_id,
                        )
                    )
        return issues

    def status(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        del arguments
        git_root = context.workspace_manager.git_root(context.workspace)
        if git_root is None:
            _log_tool_debug(
                context,
                "workspace_git.status.no_repository",
                "Workspace root is not inside an allowed git repository.",
                workspace_root=context.workspace.root,
            )
            return {
                "git_repository": False,
                "status": "",
                "workspace_root": str(context.workspace.root),
            }
        output = _run_workspace_git(["status", "--short"], context=context)
        _log_tool_debug(
            context,
            "workspace_git.status",
            "Read workspace git status.",
            workspace_root=context.workspace.root,
            git_root=git_root,
            changed_paths=len([line for line in output.splitlines() if line.strip()]),
        )
        return {
            "git_repository": True,
            "status": output,
            "workspace_root": str(context.workspace.root),
            "git_root": str(git_root),
        }

    def run_command(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        raw_args = arguments.get("args")
        if not isinstance(raw_args, list) or not raw_args:
            raise ValueError("workspace.git.run requires a non-empty args array.")
        args = [str(item) for item in raw_args if isinstance(item, str) and item.strip()]
        if not args:
            raise ValueError("workspace.git.run requires a non-empty args array.")
        git_root = context.workspace_manager.git_root(context.workspace)
        if git_root is None:
            raise ValueError("The current workspace is not a git repository.")
        command = ["git", *args]
        if context.dry_run:
            return {
                "command": command,
                "cwd": str(context.workspace.root),
                "workspace_root": str(context.workspace.root),
                "dry_run": True,
            }
        _log_tool_info(
            context,
            "workspace_git.run",
            "Running workspace git command.",
            args=args,
            workspace_root=context.workspace.root,
            git_root=git_root,
        )
        process = _run_workspace_git_process(args, context=context)
        return {
            "command": command,
            "cwd": str(context.workspace.root),
            "workspace_root": str(context.workspace.root),
            "git_root": str(git_root),
            "exit_code": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
        }

    def diff(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        git_root = context.workspace_manager.git_root(context.workspace)
        if git_root is None:
            _log_tool_debug(
                context,
                "workspace_git.diff.no_repository",
                "Workspace root is not inside an allowed git repository.",
                workspace_root=context.workspace.root,
            )
            return {
                "git_repository": False,
                "diff": "",
                "workspace_root": str(context.workspace.root),
            }
        revision = arguments.get("revision")
        args = ["diff"]
        if isinstance(revision, str) and revision:
            args.append(revision)
        output = _run_workspace_git(args, context=context)
        _log_tool_debug(
            context,
            "workspace_git.diff",
            "Read workspace git diff.",
            workspace_root=context.workspace.root,
            git_root=git_root,
            revision=revision if isinstance(revision, str) else "",
        )
        return {
            "git_repository": True,
            "diff": output,
            "workspace_root": str(context.workspace.root),
            "git_root": str(git_root),
        }

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
        git_root = context.workspace_manager.git_root(context.workspace)
        if git_root is None:
            raise ValueError("The current workspace is not a git repository.")
        relative = str(path.relative_to(context.workspace.root))
        _log_tool_info(
            context,
            "workspace_git.restore_path",
            "Restoring workspace path from HEAD.",
            path=relative,
            workspace_root=context.workspace.root,
            git_root=git_root,
        )
        _run_workspace_git(
            ["restore", "--worktree", "--source=HEAD", "--", relative],
            context=context,
        )
        return {"path": relative, "restored": True, "git_root": str(git_root)}


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
        metadata = arguments.get("metadata")
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
            metadata=dict(metadata) if isinstance(metadata, dict) else {},
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
            config_fields=[
                ConfigFieldSpec(
                    key="token_secret",
                    label="GitHub token",
                    help_text=(
                        "Tool secret name that stores a GitHub personal access token "
                        "or GitHub App installation token."
                    ),
                    value_type="secret",
                    category="connection",
                    secret=True,
                ),
                ConfigFieldSpec(
                    key="base_url",
                    label="GitHub API URL",
                    help_text=(
                        "GitHub API base URL. Use https://api.github.com for GitHub.com "
                        "or your /api/v3 URL for GitHub Enterprise."
                    ),
                    value_type="string",
                    category="connection",
                ),
                ConfigFieldSpec(
                    key="timeout_seconds",
                    label="Request timeout",
                    help_text="HTTP timeout for GitHub API requests.",
                    value_type="integer",
                    category="advanced",
                ),
            ],
            functions=[
                ToolFunctionManifest(
                    function_name="github.api.get_repository",
                    binding="get_repository",
                    description="Fetch repository metadata from the GitHub API.",
                    input_schema={"type": "object"},
                    output_schema={"type": "object"},
                    permissions=["github.read"],
                    secret_bindings=["token_secret"],
                ),
                ToolFunctionManifest(
                    function_name="github.api.get_authenticated_user",
                    binding="get_authenticated_user",
                    description=(
                        "Fetch the authenticated GitHub user for the configured token."
                    ),
                    input_schema={"type": "object"},
                    output_schema={"type": "object"},
                    permissions=["github.read"],
                    secret_bindings=["token_secret"],
                ),
                ToolFunctionManifest(
                    function_name="github.api.list_repositories",
                    binding="list_repositories",
                    description=(
                        "List repositories visible to the authenticated GitHub user."
                    ),
                    input_schema={"type": "object"},
                    output_schema={"type": "object"},
                    permissions=["github.read"],
                    secret_bindings=["token_secret"],
                ),
                ToolFunctionManifest(
                    function_name="github.api.list_issues",
                    binding="list_issues",
                    description="List repository issues through the GitHub API.",
                    input_schema={"type": "object"},
                    output_schema={"type": "object"},
                    permissions=["github.read"],
                    secret_bindings=["token_secret"],
                ),
                ToolFunctionManifest(
                    function_name="github.api.create_issue",
                    binding="create_issue",
                    description="Create a repository issue through the GitHub API.",
                    input_schema={"type": "object"},
                    output_schema={"type": "object"},
                    permissions=["github.write"],
                    secret_bindings=["token_secret"],
                    side_effect="external",
                    approval_policy="required",
                    dry_run_supported=True,
                ),
                ToolFunctionManifest(
                    function_name="github.api.add_issue_comment",
                    binding="add_issue_comment",
                    description="Add a comment to a repository issue through the GitHub API.",
                    input_schema={"type": "object"},
                    output_schema={"type": "object"},
                    permissions=["github.write"],
                    secret_bindings=["token_secret"],
                    side_effect="external",
                    approval_policy="required",
                    dry_run_supported=True,
                ),
                ToolFunctionManifest(
                    function_name="github.api.request",
                    binding="request",
                    description="Send a structured request to the configured GitHub API.",
                    input_schema={"type": "object"},
                    output_schema={"type": "object"},
                    permissions=["github.read", "github.write"],
                    secret_bindings=["token_secret"],
                    side_effect="external",
                    approval_policy="policy",
                    dry_run_supported=True,
                ),
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
        base_url = config.get("base_url")
        if base_url is not None and (not isinstance(base_url, str) or not base_url.strip()):
            issues.append(
                CheckIssue(
                    severity="error",
                    code="tool.github.invalid_base_url",
                    message="github.api base_url must be a non-empty string when provided.",
                    source=tool_id,
                )
            )
        timeout_seconds = config.get("timeout_seconds")
        if timeout_seconds is not None and not _github_timeout_is_valid(timeout_seconds):
            issues.append(
                CheckIssue(
                    severity="error",
                    code="tool.github.invalid_timeout",
                    message="github.api timeout_seconds must be a positive number.",
                    source=tool_id,
                )
            )
        return issues

    def assess_risk(
        self,
        function_name: str,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> ToolRiskDecision:
        del context
        if function_name == "github.api.request":
            try:
                method = _github_method(arguments.get("method", "GET"))
            except ValueError:
                return ToolRiskDecision(approval_policy="required", checkpoint_required=False)
            if method in {"GET", "HEAD"}:
                return ToolRiskDecision(approval_policy="never", checkpoint_required=False)
            return ToolRiskDecision(
                approval_policy="required",
                reason=f"Approve GitHub {method} request?",
                checkpoint_required=False,
            )
        if function_name in {"github.api.create_issue", "github.api.add_issue_comment"}:
            return ToolRiskDecision(approval_policy="required", checkpoint_required=False)
        return ToolRiskDecision(approval_policy="inherit", checkpoint_required=False)

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

        if context.dry_run:
            return {
                "method": "GET",
                "url": _github_endpoint(context, f"/repos/{owner}/{repo}"),
                "dry_run": True,
            }

        payload = self._github_request(context, "GET", f"/repos/{owner}/{repo}")
        if not isinstance(payload, dict):
            raise ValueError("GitHub API returned an unexpected payload.")
        return {
            "full_name": payload.get("full_name"),
            "private": payload.get("private"),
            "default_branch": payload.get("default_branch"),
            "description": payload.get("description"),
            "html_url": payload.get("html_url"),
        }

    def get_authenticated_user(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        del arguments
        if context.dry_run:
            return {
                "method": "GET",
                "url": _github_endpoint(context, "/user"),
                "dry_run": True,
            }

        payload = self._github_request(context, "GET", "/user")
        if not isinstance(payload, dict):
            raise ValueError("GitHub API returned an unexpected user payload.")
        return {
            "login": payload.get("login"),
            "id": payload.get("id"),
            "name": payload.get("name"),
            "html_url": payload.get("html_url"),
            "type": payload.get("type"),
            "site_admin": payload.get("site_admin"),
        }

    def list_repositories(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        query = _github_query(
            {
                "visibility": _github_optional_string(arguments.get("visibility")),
                "affiliation": _github_optional_string(arguments.get("affiliation")),
                "type": _github_optional_string(arguments.get("type")),
                "sort": _github_optional_string(arguments.get("sort")),
                "direction": _github_optional_string(arguments.get("direction")),
                "per_page": arguments.get("per_page", 30),
                "page": arguments.get("page"),
            }
        )
        if context.dry_run:
            return {
                "method": "GET",
                "url": _github_endpoint(context, "/user/repos", query),
                "dry_run": True,
            }

        payload = self._github_request(context, "GET", "/user/repos", query=query)
        if not isinstance(payload, list):
            raise ValueError("GitHub API returned an unexpected repositories payload.")
        repositories = [
            {
                "full_name": item.get("full_name"),
                "private": item.get("private"),
                "default_branch": item.get("default_branch"),
                "description": item.get("description"),
                "html_url": item.get("html_url"),
                "archived": item.get("archived"),
                "fork": item.get("fork"),
            }
            for item in payload
            if isinstance(item, dict)
        ]
        return {"repositories": repositories}

    def list_issues(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        owner, repo = _github_owner_repo(arguments, "github.api.list_issues")
        query = _github_query(
            {
                "state": _github_optional_string(arguments.get("state")) or "open",
                "labels": _github_optional_string(arguments.get("labels")),
                "since": _github_optional_string(arguments.get("since")),
                "per_page": arguments.get("per_page", 30),
            }
        )
        path = f"/repos/{owner}/{repo}/issues"
        if context.dry_run:
            return {"method": "GET", "url": _github_endpoint(context, path, query), "dry_run": True}

        payload = self._github_request(context, "GET", path, query=query)
        if not isinstance(payload, list):
            raise ValueError("GitHub API returned an unexpected issues payload.")
        issues = [
            {
                "number": item.get("number"),
                "title": item.get("title"),
                "state": item.get("state"),
                "html_url": item.get("html_url"),
                "user": (
                    item.get("user", {}).get("login")
                    if isinstance(item.get("user"), dict)
                    else None
                ),
                "pull_request": "pull_request" in item,
            }
            for item in payload
            if isinstance(item, dict)
        ]
        return {"issues": issues}

    def create_issue(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        owner, repo = _github_owner_repo(arguments, "github.api.create_issue")
        title = _github_required_string(arguments.get("title"), "title", "github.api.create_issue")
        body = _github_optional_string(arguments.get("body"))
        payload: dict[str, object] = {"title": title}
        if body is not None:
            payload["body"] = body
        for key in ("labels", "assignees"):
            values = _github_string_list(arguments.get(key))
            if values:
                payload[key] = values
        path = f"/repos/{owner}/{repo}/issues"
        if context.dry_run:
            return {
                "method": "POST",
                "url": _github_endpoint(context, path),
                "body": payload,
                "dry_run": True,
            }

        response = self._github_request(context, "POST", path, body=payload)
        if not isinstance(response, dict):
            raise ValueError("GitHub API returned an unexpected issue payload.")
        return _github_issue_summary(response)

    def add_issue_comment(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        owner, repo = _github_owner_repo(arguments, "github.api.add_issue_comment")
        issue_number = _github_positive_int(
            arguments.get("issue_number"),
            "issue_number",
            "github.api.add_issue_comment",
        )
        body = _github_required_string(
            arguments.get("body"),
            "body",
            "github.api.add_issue_comment",
        )
        path = f"/repos/{owner}/{repo}/issues/{issue_number}/comments"
        request_body = {"body": body}
        if context.dry_run:
            return {
                "method": "POST",
                "url": _github_endpoint(context, path),
                "body": request_body,
                "dry_run": True,
            }

        response = self._github_request(context, "POST", path, body=request_body)
        if not isinstance(response, dict):
            raise ValueError("GitHub API returned an unexpected comment payload.")
        return {
            "id": response.get("id"),
            "html_url": response.get("html_url"),
            "body": response.get("body"),
        }

    def request(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        method = _github_method(arguments.get("method", "GET"))
        path = _github_required_string(arguments.get("path"), "path", "github.api.request")
        query = _github_query(arguments.get("query", {}))
        body = arguments.get("json", arguments.get("body"))
        if body is not None and not isinstance(body, (dict, list)):
            raise ValueError("github.api.request body/json must be an object or list.")
        _log_tool_info(
            context,
            "github_api.request",
            "Preparing GitHub API request.",
            method=method,
            path=path,
            query_keys=sorted(query),
            has_body=body is not None,
            dry_run=context.dry_run,
        )
        if context.dry_run:
            return {
                "method": method,
                "url": _github_endpoint(context, path, query),
                "body": body,
                "dry_run": True,
            }
        response = self._github_request(context, method, path, query=query, body=body)
        _log_tool_info(
            context,
            "github_api.request.completed",
            "Completed GitHub API request.",
            method=method,
            path=path,
        )
        return {
            "method": method,
            "path": path,
            "response": response,
        }

    def _github_request(
        self,
        context: ToolExecutionContext,
        method: str,
        path: str,
        *,
        query: Mapping[str, object] | None = None,
        body: object = None,
    ) -> object:
        url = _github_endpoint(context, path, query)
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "nagient",
        }
        token = _github_token(context)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener(request, timeout=_github_timeout_seconds(context.config)) as response:
                raw_payload = response.read().decode("utf-8")
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")[:400]
            raise ValueError(f"GitHub API returned HTTP {exc.code}: {error_body}") from exc
        except URLError as exc:
            raise ValueError(f"GitHub API request failed: {exc.reason}") from exc
        if not raw_payload.strip():
            return {}
        try:
            return json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            raise ValueError("GitHub API returned invalid JSON.") from exc


def builtin_tools() -> list[LoadedToolPlugin]:
    plugins: list[BaseToolPlugin] = [
        WorkspaceFsToolPlugin(),
        WorkspaceShellToolPlugin(),
        WorkspaceGitToolPlugin(),
        TransportInteractionToolPlugin(),
        TransportRouterToolPlugin(),
        AgentMemoryToolPlugin(),
        SystemBackupToolPlugin(),
        SystemReconcileToolPlugin(),
        SystemJobsToolPlugin(),
        SystemConfigToolPlugin(),
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


def _string_config(config: Mapping[str, object], key: str) -> str | None:
    value = config.get(key)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _github_owner_repo(
    arguments: Mapping[str, object],
    function_name: str,
) -> tuple[str, str]:
    owner = _github_required_string(arguments.get("owner"), "owner", function_name)
    repo = _github_required_string(arguments.get("repo"), "repo", function_name)
    return owner, repo


def _github_required_string(value: object, field_name: str, function_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{function_name} requires {field_name}.")
    return value.strip()


def _github_optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _github_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raise ValueError("GitHub string list fields must be strings or arrays.")


def _github_positive_int(value: object, field_name: str, function_name: str) -> int:
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        if parsed > 0:
            return parsed
    raise ValueError(f"{function_name} requires positive integer {field_name}.")


def _github_method(value: object) -> str:
    method = str(value).strip().upper()
    if method not in {"GET", "POST", "PATCH", "PUT", "DELETE", "HEAD"}:
        raise ValueError(
            "github.api.request method must be GET, POST, PATCH, PUT, DELETE, or HEAD."
        )
    return method


def _github_base_url(config: Mapping[str, object]) -> str:
    base_url = config.get("base_url", "https://api.github.com")
    if not isinstance(base_url, str) or not base_url.strip():
        return "https://api.github.com"
    return base_url.strip().rstrip("/")


def _github_endpoint(
    context: ToolExecutionContext,
    path: str,
    query: Mapping[str, object] | None = None,
) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    url = f"{_github_base_url(context.config)}{normalized_path}"
    query_string = urlencode(
        {
            str(key): str(value)
            for key, value in (query or {}).items()
            if value is not None and str(value).strip()
        }
    )
    if query_string:
        return f"{url}?{query_string}"
    return url


def _github_query(value: object) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("GitHub query must be an object.")
    return {
        str(key): item
        for key, item in value.items()
        if item is not None and str(item).strip()
    }


def _github_token_secret(config: Mapping[str, object]) -> str:
    token_secret = config.get("token_secret", "GITHUB_TOKEN")
    if not isinstance(token_secret, str) or not token_secret.strip():
        return "GITHUB_TOKEN"
    return token_secret.strip()


def _github_token(context: ToolExecutionContext) -> str:
    secret_name = _github_token_secret(context.config)
    return context.secret_broker.resolve_secret(secret_name, scope_hint="tool")


def _github_timeout_seconds(config: Mapping[str, object]) -> float:
    value = config.get("timeout_seconds", 15)
    if isinstance(value, bool):
        return 15.0
    if isinstance(value, int | float) and value > 0:
        return float(value)
    if isinstance(value, str):
        try:
            parsed = float(value.strip())
        except ValueError:
            return 0.0
        if parsed > 0:
            return parsed
    return 15.0


def _github_timeout_is_valid(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int | float):
        return value > 0
    if isinstance(value, str):
        try:
            return float(value.strip()) > 0
        except ValueError:
            return False
    return False


def _github_issue_summary(payload: Mapping[str, object]) -> dict[str, object]:
    return {
        "number": payload.get("number"),
        "title": payload.get("title"),
        "state": payload.get("state"),
        "html_url": payload.get("html_url"),
        "body": payload.get("body"),
    }


def _run_workspace_git(
    args: list[str],
    *,
    context: ToolExecutionContext,
) -> str:
    process = _run_workspace_git_process(args, context=context)
    if process.returncode != 0:
        raise ValueError(process.stderr.strip() or process.stdout.strip())
    return process.stdout


def _run_workspace_git_process(
    args: list[str],
    *,
    context: ToolExecutionContext,
) -> subprocess.CompletedProcess[str]:
    env, cleanup_paths = _workspace_git_env(
        workspace_root=context.workspace.root,
        config=context.config,
        secret_broker=context.secret_broker,
    )
    try:
        return subprocess.run(
            ["git", *args],
            cwd=context.workspace.root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        for path in cleanup_paths:
            with contextlib.suppress(FileNotFoundError):
                path.unlink()


def _log_tool_debug(
    context: ToolExecutionContext,
    event: str,
    message: str,
    **fields: object,
) -> None:
    _log_tool(context, "debug", event, message, **fields)


def _log_tool_info(
    context: ToolExecutionContext,
    event: str,
    message: str,
    **fields: object,
) -> None:
    _log_tool(context, "info", event, message, **fields)


def _log_tool(
    context: ToolExecutionContext,
    level: str,
    event: str,
    message: str,
    **fields: object,
) -> None:
    logger = context.logger
    if logger is None:
        return
    log_method = getattr(logger, level, None)
    if not callable(log_method):
        return
    log_method(
        event,
        message,
        tool_id=context.tool_id,
        plugin_id=context.plugin_id,
        session_id=context.session_id or "",
        transport_id=context.transport_id or "",
        **fields,
    )


def _workspace_git_env(
    *,
    workspace_root: Path,
    config: Mapping[str, object],
    secret_broker: object,
) -> tuple[dict[str, str], list[Path]]:
    env = _shell_env(workspace_root)
    cleanup_paths: list[Path] = []
    author_name = _string_config(config, "author_name")
    author_email = _string_config(config, "author_email")
    committer_name = _string_config(config, "committer_name") or author_name
    committer_email = _string_config(config, "committer_email") or author_email
    username = _string_config(config, "username")
    token_secret = _string_config(config, "token_secret")
    password_secret = _string_config(config, "password_secret")
    secret_name = token_secret or password_secret

    if author_name:
        env["GIT_AUTHOR_NAME"] = author_name
    if author_email:
        env["GIT_AUTHOR_EMAIL"] = author_email
    if committer_name:
        env["GIT_COMMITTER_NAME"] = committer_name
    if committer_email:
        env["GIT_COMMITTER_EMAIL"] = committer_email

    if username:
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"] = "credential.username"
        env["GIT_CONFIG_VALUE_0"] = username

    if secret_name and hasattr(secret_broker, "resolve_secret"):
        password = secret_broker.resolve_secret(secret_name, scope_hint="tool")
        if isinstance(password, str) and password:
            askpass_path = _write_git_askpass_script()
            cleanup_paths.append(askpass_path)
            env["GIT_TERMINAL_PROMPT"] = "0"
            env["GIT_ASKPASS"] = str(askpass_path)
            env["SSH_ASKPASS"] = str(askpass_path)
            env["NAGIENT_GIT_PASSWORD"] = password
            if username:
                env["NAGIENT_GIT_USERNAME"] = username

    return env, cleanup_paths


def _write_git_askpass_script() -> Path:
    script = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix="nagient-git-askpass-",
        suffix=".sh",
        delete=False,
    )
    try:
        script.write(
            "\n".join(
                [
                    "#!/bin/sh",
                    'case "$1" in',
                    '  *Username*|*username*) printf "%s\\n" "${NAGIENT_GIT_USERNAME:-}" ;;',
                    '  *) printf "%s\\n" "${NAGIENT_GIT_PASSWORD:-}" ;;',
                    "esac",
                    "",
                ]
            )
        )
    finally:
        script.close()
    path = Path(script.name)
    path.chmod(0o700)
    return path


def _plan_shell_command(
    command: str,
    *,
    timeout_seconds: int,
    default_ping_count: int,
    normalize_infinite_commands: bool,
    enforce_finite_commands: bool,
) -> _ShellCommandPlan:
    normalized = command.strip()
    for prefix in _SHELL_BLOCKED_PREFIXES:
        if re.match(rf"^\s*{re.escape(prefix)}\b", normalized):
            return _ShellCommandPlan(
                effective_command=command,
                blocked_reason=(
                    f"Command {prefix!r} is interactive or continuous. "
                    "Use a finite non-interactive variant instead."
                ),
            )

    if re.match(r"^\s*tail\b", normalized) and re.search(
        r"(^|\s)(-f|-F|--follow(?:=\S+)?)($|\s)",
        normalized,
    ):
        return _ShellCommandPlan(
            effective_command=command,
            blocked_reason=(
                "Commands that continuously follow output are not allowed. "
                "Use a finite tail invocation instead."
            ),
        )

    notes: list[str] = []
    effective_command = command
    if re.match(r"^\s*ping6?\b", normalized):
        has_count = re.search(r"(^|\s)(-c|--count)(?:\s+|=)\d+", normalized) is not None
        if not has_count:
            if normalize_infinite_commands:
                effective_command = re.sub(
                    r"^(\s*ping6?\b)",
                    rf"\1 -c {default_ping_count}",
                    command,
                    count=1,
                )
                notes.append(
                    f"Added `-c {default_ping_count}` so ping exits on its own."
                )
            elif enforce_finite_commands:
                return _ShellCommandPlan(
                    effective_command=command,
                    blocked_reason=(
                        "ping must include a finite count such as `-c 4` when used by the agent."
                    ),
                )
    if re.match(r"^\s*curl\b", normalized):
        has_max_time = re.search(r"(^|\s)(-m|--max-time)(?:\s+|=)\d+", normalized) is not None
        if not has_max_time and normalize_infinite_commands:
            effective_command = re.sub(
                r"^(\s*curl\b)",
                rf"\1 --max-time {timeout_seconds}",
                effective_command,
                count=1,
            )
            notes.append(
                f"Added `--max-time {timeout_seconds}` so curl stays within the shell budget."
            )
    return _ShellCommandPlan(
        effective_command=effective_command,
        notes=notes,
    )


def _run_shell_command(
    command: str,
    *,
    cwd: Path,
    env: Mapping[str, str],
    timeout_seconds: int,
    grace_period_seconds: int,
) -> _ShellProcessResult:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        shell=True,
        executable="/bin/sh",
        env=dict(env),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        start_new_session=True,
    )
    timed_out = False
    stdout_bytes = b""
    stderr_bytes = b""
    try:
        stdout_bytes, stderr_bytes = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout_bytes = exc.stdout or b""
        stderr_bytes = exc.stderr or b""
        _terminate_shell_process(process)
        try:
            flushed_stdout, flushed_stderr = process.communicate(timeout=grace_period_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            flushed_stdout, flushed_stderr = process.communicate()
        stdout_bytes += flushed_stdout or b""
        stderr_bytes += flushed_stderr or b""
    return _ShellProcessResult(
        exit_code=None if timed_out else process.returncode,
        stdout=stdout_bytes.decode("utf-8", errors="replace"),
        stderr=stderr_bytes.decode("utf-8", errors="replace"),
        timed_out=timed_out,
    )


def _terminate_shell_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if hasattr(os, "killpg"):
        try:
            os.killpg(process.pid, signal.SIGTERM)
            return
        except ProcessLookupError:
            return
        except OSError:
            pass
    process.terminate()


def _truncate_text(value: str, limit: int) -> tuple[str, bool]:
    if limit <= 0 or len(value) <= limit:
        return value, False
    return value[:limit], True


def _positive_int(value: object, *, default: int) -> int:
    if isinstance(value, int) and value > 0:
        return value
    return default


def _bool_config(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _run_git(args: list[str], *, cwd: Path, env: Mapping[str, str] | None = None) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=dict(env or _shell_env(cwd)),
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
