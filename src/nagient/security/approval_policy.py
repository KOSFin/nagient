from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nagient.domain.entities.tooling import ToolExecutionRequest, ToolFunctionManifest
from nagient.tools.base import ToolRiskDecision


@dataclass(frozen=True)
class ApprovalContext:
    expected_by_user: bool = False
    reason: str = ""
    on_success: str = "message"
    on_success_message: str = ""
    on_error: str = "resume_model"
    on_error_message: str = ""
    metadata: dict[str, object] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, object]:
        return {
            "expected_by_user": self.expected_by_user,
            "reason": self.reason,
            "on_success": self.on_success,
            "on_success_message": self.on_success_message,
            "on_error": self.on_error,
            "on_error_message": self.on_error_message,
            **dict(self.metadata),
        }


@dataclass(frozen=True)
class ApprovalPolicyDecision:
    policy: str
    checkpoint_required: bool
    reason: str
    context: ApprovalContext
    sanitized_arguments: dict[str, object]


class ApprovalPolicyEngine:
    def decide(
        self,
        *,
        request: ToolExecutionRequest,
        function: ToolFunctionManifest,
        risk: ToolRiskDecision,
    ) -> ApprovalPolicyDecision:
        sanitized_arguments, approval_context = extract_approval_context(request.arguments)
        policy = function.approval_policy
        if risk.approval_policy != "inherit":
            policy = risk.approval_policy

        checkpoint_required = (
            risk.checkpoint_required
            if risk.checkpoint_required is not None
            else function.side_effect in {"write", "destructive", "system"}
        )
        reason = risk.reason or f"Approve execution of {request.function_name!r}?"

        if (
            policy == "required"
            and approval_context.expected_by_user
            and _can_auto_approve_expected_action(request.function_name, sanitized_arguments)
        ):
            policy = "never"
            reason = approval_context.reason or "Action matches the user's requested plan."

        return ApprovalPolicyDecision(
            policy=policy,
            checkpoint_required=checkpoint_required,
            reason=reason,
            context=approval_context,
            sanitized_arguments=sanitized_arguments,
        )


def extract_approval_context(
    arguments: dict[str, object],
) -> tuple[dict[str, object], ApprovalContext]:
    sanitized = dict(arguments)
    raw_context = sanitized.pop("approval_context", None)
    if not isinstance(raw_context, dict):
        return sanitized, ApprovalContext()

    on_success = _enum_value(
        raw_context.get("on_success"),
        allowed={"message", "resume_model", "none"},
        default="message",
    )
    on_error = _enum_value(
        raw_context.get("on_error"),
        allowed={"resume_model", "message", "none"},
        default="resume_model",
    )
    metadata = raw_context.get("metadata")
    return sanitized, ApprovalContext(
        expected_by_user=bool(raw_context.get("expected_by_user", False)),
        reason=_string(raw_context.get("reason")),
        on_success=on_success,
        on_success_message=_string(raw_context.get("on_success_message")),
        on_error=on_error,
        on_error_message=_string(raw_context.get("on_error_message")),
        metadata={str(key): value for key, value in metadata.items()}
        if isinstance(metadata, dict)
        else {},
    )


def _can_auto_approve_expected_action(
    function_name: str,
    arguments: dict[str, object],
) -> bool:
    if function_name == "workspace.git.run":
        args = arguments.get("args")
        if not isinstance(args, list) or not args:
            return False
        subcommand = str(args[0]).strip().lower()
        return subcommand in {"clone", "add", "commit", "push", "status", "diff", "log"}

    if function_name == "github.api.request":
        method = str(arguments.get("method", "GET")).strip().upper()
        path = str(arguments.get("path", "")).strip()
        return method in {"GET", "HEAD", "POST", "PATCH", "PUT"} and path.startswith("/")

    if function_name in {
        "github.api.create_issue",
        "github.api.add_issue_comment",
        "transport.router.send_message",
        "transport.router.send_notification",
        "transport.router.send_typing",
    }:
        return True

    return False


def _enum_value(value: object, *, allowed: set[str], default: str) -> str:
    normalized = _string(value)
    return normalized if normalized in allowed else default


def _string(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()
