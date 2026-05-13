from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from temporalio import activity
from temporalio.exceptions import ApplicationError

from aegisflow_workflow_engine.domain import (
    OutboxPublishStatus,
    RecoveryActionStatus,
    RecoveryActionType,
    TimelineEntryType,
    WorkflowEventType,
    WorkflowState,
)
from aegisflow_workflow_engine.persistence.database import SessionLocal
from aegisflow_workflow_engine.persistence.models import (
    WorkflowEventOutbox,
    WorkflowRecoveryAction,
    WorkflowRecord,
    WorkflowStateTransition,
    WorkflowTimelineEntry,
)
from aegisflow_workflow_engine.telemetry import instrument_activity


@activity.defn(name="reconcile_workflow_projection")
@instrument_activity("reconcile_workflow_projection")
async def reconcile_workflow_projection(payload: dict) -> dict:
    workflow_id = payload["workflow_id"]
    recovery_action_id = payload.get("recovery_action_id") or str(uuid4())
    correlation_id = payload["correlation_id"]
    requested_by = _require_text(payload, "requested_by")
    reason = _require_text(payload, "reason")
    action_type = RecoveryActionType(payload["action_type"])
    dry_run = bool(payload.get("dry_run", False))

    if action_type != RecoveryActionType.reconcile_workflow_projection:
        raise ApplicationError(
            f"Unsupported workflow recovery action {action_type.value}",
            non_retryable=True,
        )

    async with SessionLocal() as session:
        workflow = await session.get(WorkflowRecord, workflow_id)
        if workflow is None:
            raise ApplicationError(f"Workflow {workflow_id} was not found", non_retryable=True)

        latest_transition = await _latest_transition(session, workflow_id)
        if latest_transition is None:
            raise ApplicationError(
                f"Workflow {workflow_id} has no transition evidence to reconcile from",
                non_retryable=True,
            )

        current_state = workflow.state
        proposed_state = latest_transition.new_state
        if dry_run:
            return {
                "workflow_id": workflow_id,
                "recovery_action_id": recovery_action_id,
                "dry_run": True,
                "allowed": current_state != proposed_state,
                "current_state": current_state,
                "proposed_state": proposed_state,
                "engine_owned_mutation": False,
            }

        now = datetime.now(timezone.utc)
        recovery_action = await session.get(WorkflowRecoveryAction, recovery_action_id)
        if recovery_action is None:
            recovery_action = WorkflowRecoveryAction(
                recovery_action_id=recovery_action_id,
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                action_type=action_type.value,
                target_resource_type="workflow_record",
                target_resource_id=workflow_id,
                status=RecoveryActionStatus.running.value,
                requested_by=requested_by,
                reason=reason,
                started_at=now,
                completed_at=None,
                result_metadata={},
                created_at=now,
            )
            session.add(recovery_action)

        workflow.state = proposed_state
        workflow.updated_at = now
        if proposed_state == WorkflowState.completed.value:
            workflow.completed_at = now
        if proposed_state == WorkflowState.failed.value:
            workflow.failed_at = now

        recovery_action.status = RecoveryActionStatus.completed.value
        recovery_action.completed_at = now
        recovery_action.result_metadata = {
            **recovery_action.result_metadata,
            "current_state": current_state,
            "reconciled_state": proposed_state,
            "latest_transition_id": latest_transition.transition_id,
            "engine_owned_mutation": current_state != proposed_state,
            "sensitive_payloads_persisted": False,
        }

        session.add(
            WorkflowTimelineEntry(
                timeline_entry_id=str(uuid4()),
                workflow_id=workflow_id,
                entry_type=TimelineEntryType.recovery_action_recorded.value,
                message="Workflow projection recovery completed.",
                state=proposed_state,
                correlation_id=correlation_id,
                created_by="workflow-engine",
                entry_metadata={
                    "recovery_action_id": recovery_action_id,
                    "action_type": action_type.value,
                    "prior_state": current_state,
                    "reconciled_state": proposed_state,
                    "requested_by": requested_by,
                    "reason_present": True,
                },
                created_at=now,
            )
        )

        event_id = f"{workflow_id}:{WorkflowEventType.recovery_action_completed.value}:{recovery_action_id}"
        if await session.get(WorkflowEventOutbox, event_id) is None:
            session.add(
                WorkflowEventOutbox(
                    event_id=event_id,
                    event_type=WorkflowEventType.recovery_action_completed.value,
                    event_version="1",
                    workflow_id=workflow_id,
                    correlation_id=correlation_id,
                    payload={
                        "workflow_id": workflow_id,
                        "recovery_action_id": recovery_action_id,
                        "action_type": action_type.value,
                        "prior_state": current_state,
                        "reconciled_state": proposed_state,
                    },
                    publish_status=OutboxPublishStatus.pending.value,
                    retry_count=0,
                    last_error=None,
                    created_at=now,
                    published_at=None,
                )
            )

        await session.commit()

    return {
        "workflow_id": workflow_id,
        "recovery_action_id": recovery_action_id,
        "dry_run": False,
        "current_state": current_state,
        "reconciled_state": proposed_state,
        "engine_owned_mutation": current_state != proposed_state,
    }


async def _latest_transition(session, workflow_id: str) -> WorkflowStateTransition | None:
    result = await session.execute(
        select(WorkflowStateTransition)
        .where(WorkflowStateTransition.workflow_id == workflow_id)
        .order_by(WorkflowStateTransition.created_at.desc(), WorkflowStateTransition.transition_id.desc())
    )
    return result.scalars().first()


def _require_text(payload: dict, field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise ApplicationError(f"Recovery command requires {field}", non_retryable=True)
    return value
