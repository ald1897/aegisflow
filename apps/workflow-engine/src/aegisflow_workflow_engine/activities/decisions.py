from sqlalchemy import select
from temporalio import activity
from temporalio.exceptions import ApplicationError

from aegisflow_workflow_engine.activities.approvals import record_approval_decision
from aegisflow_workflow_engine.activities.state_transitions import advance_workflow_state
from aegisflow_workflow_engine.domain import WorkflowState
from aegisflow_workflow_engine.persistence.database import SessionLocal
from aegisflow_workflow_engine.persistence.models import WorkflowRecord
from aegisflow_workflow_engine.telemetry import instrument_activity, set_span_attributes


DECISION_TO_STATE = {
    "APPROVED": WorkflowState.approved,
    "REJECTED": WorkflowState.rejected,
}


@activity.defn(name="apply_human_review_decision")
@instrument_activity("apply_human_review_decision")
async def apply_human_review_decision(payload: dict) -> dict:
    workflow_id = payload["workflow_id"]
    correlation_id = payload["correlation_id"]
    decision = payload["decision"]
    target_state = DECISION_TO_STATE.get(decision)
    if target_state is None:
        raise ApplicationError("Approval decision must be APPROVED or REJECTED", non_retryable=True)

    current_state = await _get_workflow_state(workflow_id)
    allowed_retry_states = {WorkflowState.human_review_required, target_state, WorkflowState.completed}
    if current_state not in allowed_retry_states:
        raise ApplicationError(
            f"Workflow {workflow_id} is not in a human review decision state",
            non_retryable=True,
        )

    approval_result = await record_approval_decision(payload)

    if current_state == WorkflowState.human_review_required:
        await advance_workflow_state(
            {
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "target_state": target_state.value,
                "transition_reason": f"human_review_{decision.lower()}",
                "message": f"Human review decision applied: {decision.lower()}",
            }
        )
        current_state = target_state

    if current_state == target_state:
        await advance_workflow_state(
            {
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "target_state": WorkflowState.completed.value,
                "transition_reason": "human_review_decision_completed",
                "message": "Workflow completed after human review decision",
            }
        )

    final_state = await _get_workflow_state(workflow_id)
    set_span_attributes(
        {
            "approval_id": payload["approval_id"],
            "approval.decision": decision,
            "workflow.final_state": final_state.value,
            "idempotent": approval_result["idempotent"] and final_state == WorkflowState.completed,
        }
    )
    return {
        "workflow_id": workflow_id,
        "approval_id": payload["approval_id"],
        "decision": decision,
        "state": final_state.value,
        "idempotent": approval_result["idempotent"] and final_state == WorkflowState.completed,
    }


async def _get_workflow_state(workflow_id: str) -> WorkflowState:
    async with SessionLocal() as session:
        result = await session.execute(
            select(WorkflowRecord.state).where(WorkflowRecord.workflow_id == workflow_id)
        )
        state = result.scalar_one_or_none()
        if state is None:
            raise ApplicationError(f"Workflow {workflow_id} was not found", non_retryable=True)
        return WorkflowState(state)
