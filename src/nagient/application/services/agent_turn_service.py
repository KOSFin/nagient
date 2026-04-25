from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nagient.domain.entities.agent_runtime import AgentTurnRequest, AgentTurnResult
from nagient.domain.entities.security import ApprovalRequest, InteractionRequest
from nagient.domain.entities.tooling import ToolExecutionRequest


@dataclass(frozen=True)
class AgentTurnService:
    tool_service: Any
    workflow_service: Any

    def run_turn(self, request: AgentTurnRequest) -> AgentTurnResult:
        tool_requests = [
            ToolExecutionRequest(
                tool_id=call.request.tool_id,
                function_name=call.request.function_name,
                arguments=call.request.arguments,
                dry_run=call.request.dry_run,
                batch_id=call.request.batch_id,
                session_id=request.context.session_id,
                transport_id=request.context.transport_id,
                auto_approve=call.request.auto_approve,
            )
            for call in request.assistant_response.tool_calls
        ]
        tool_results, checkpoint_id = self.tool_service.invoke_batch(tool_requests)

        stored_interactions = [
            self.workflow_service.create_interaction(
                InteractionRequest(
                    request_id=item.request_id,
                    session_id=request.context.session_id,
                    transport_id=request.context.transport_id,
                    interaction_type=item.interaction_type,
                    prompt=item.prompt,
                    status=item.status,
                    created_at=item.created_at,
                    post_submit_actions=item.post_submit_actions,
                    metadata=item.metadata,
                )
            )
            for item in request.assistant_response.interaction_requests
        ]
        stored_approvals = [
            self.workflow_service.create_approval(
                ApprovalRequest(
                    request_id=item.request_id,
                    session_id=request.context.session_id,
                    transport_id=request.context.transport_id,
                    action_label=item.action_label,
                    prompt=item.prompt,
                    status=item.status,
                    created_at=item.created_at,
                    action=item.action,
                    metadata=item.metadata,
                )
            )
            for item in request.assistant_response.approval_requests
        ]

        return AgentTurnResult(
            request_id=request.request_id,
            session_id=request.context.session_id,
            transport_id=request.context.transport_id,
            message=request.assistant_response.message,
            tool_results=tool_results,
            interaction_requests=stored_interactions,
            approval_requests=stored_approvals,
            notifications=request.assistant_response.notifications,
            config_mutations=request.assistant_response.config_mutations,
            checkpoint_id=checkpoint_id,
        )
