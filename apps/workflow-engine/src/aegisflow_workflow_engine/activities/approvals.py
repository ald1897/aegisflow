import logging
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from sqlalchemy import select
from temporalio import activity
from temporalio.exceptions import ApplicationError

from aegisflow_workflow_engine.activities.state_transitions import publish_workflow_event
from aegisflow_workflow_engine.domain import (
    OutboxPublishStatus,
    TimelineEntryType,
    WorkflowEventType,
)
from aegisflow_workflow_engine.persistence.database import SessionLocal
from aegisflow_workflow_engine.persistence.models import (
    ApprovalRecord,
    WorkflowEventOutbox,
    WorkflowRecord,
    WorkflowTimelineEntry,
)
from aegisflow_workflow_engine.metrics import record_approval_decision as record_approval_decision_metric
from aegisflow_workflow_engine.telemetry import instrument_activity, set_span_attributes

logger = logging.getLogger(__name__)

TERMINAL_DECISIONS = {"APPROVED", "REJECTED"}


@activity.defn(name="record_approval_decision")
@instrument_activity("record_approval_decision")
async def record_approval_decision(payload: dict) -> dict:
    workflow_id = payload["workflow_id"]
    correlation_id = payload["correlation_id"]
    approval_id = payload["approval_id"]
    decision = payload["decision"]
    reviewed_by = payload["reviewed_by"]
    activity_start_time = perf_counter()
    reviewed_at = _coerce_datetime(payload.get("reviewed_at")) or datetime.now(timezone.utc)
    now = datetime.now(timezone.utc)

    _validate_payload(decision=decision, reviewed_by=reviewed_by, comment=payload.get("comment"))

    existing_event_id: str | None = None
    existing_decision: str | None = None
    async with SessionLocal() as session:
        result = await session.execute(
            select(WorkflowRecord).where(WorkflowRecord.workflow_id == workflow_id)
        )
        workflow = result.scalar_one_or_none()
        if workflow is None:
            raise ApplicationError(f"Workflow {workflow_id} was not found", non_retryable=True)

        existing = await session.get(ApprovalRecord, approval_id)
        if existing is not None:
            existing_event_id = f"{workflow_id}:{WorkflowEventType.approval_decision_recorded.value}:{approval_id}"
            existing_decision = existing.decision
        else:
            duplicate_result = await session.execute(
                select(ApprovalRecord)
                .where(ApprovalRecord.workflow_id == workflow_id)
                .where(ApprovalRecord.decision.in_(TERMINAL_DECISIONS))
            )
            duplicate_decision = duplicate_result.scalar_one_or_none()
            if duplicate_decision is not None:
                raise ApplicationError(
                    f"Workflow {workflow_id} already has an approval decision",
                    non_retryable=True,
                )

            event_id = f"{workflow_id}:{WorkflowEventType.approval_decision_recorded.value}:{approval_id}"
            approval_metadata = payload.get("approval_metadata", {})

            session.add(
                ApprovalRecord(
                    approval_id=approval_id,
                    workflow_id=workflow_id,
                    correlation_id=correlation_id,
                    decision=decision,
                    decision_reason=payload["decision_reason"],
                    comment=payload["comment"],
                    reviewed_by=reviewed_by,
                    reviewed_at=reviewed_at,
                    approval_metadata=approval_metadata,
                    created_at=now,
                )
            )

            session.add(
                WorkflowTimelineEntry(
                    timeline_entry_id=str(uuid4()),
                    workflow_id=workflow_id,
                    entry_type=TimelineEntryType.approval_decision_recorded.value,
                    message=f"Human review decision recorded: {decision.lower()}",
                    state=workflow.state,
                    correlation_id=correlation_id,
                    created_by=reviewed_by,
                    entry_metadata={
                        "approval_id": approval_id,
                        "decision": decision,
                        "decision_reason": payload["decision_reason"],
                        "reviewed_by": reviewed_by,
                        "reviewed_at": reviewed_at.isoformat(),
                    },
                    created_at=reviewed_at,
                )
            )

            existing_event = await session.get(WorkflowEventOutbox, event_id)
            if existing_event is None:
                session.add(
                    WorkflowEventOutbox(
                        event_id=event_id,
                        event_type=WorkflowEventType.approval_decision_recorded.value,
                        event_version="1",
                        workflow_id=workflow_id,
                        correlation_id=correlation_id,
                        payload={
                            "workflow_id": workflow_id,
                            "correlation_id": correlation_id,
                            "approval_id": approval_id,
                            "decision": decision,
                            "decision_reason": payload["decision_reason"],
                            "reviewed_by": reviewed_by,
                            "reviewed_at": reviewed_at.isoformat(),
                            "workflow_state": workflow.state,
                        },
                        publish_status=OutboxPublishStatus.pending.value,
                        retry_count=0,
                        last_error=None,
                        created_at=reviewed_at,
                        published_at=None,
                    )
                )

            await session.commit()

    if existing_event_id is not None:
        await publish_workflow_event(existing_event_id)
        record_approval_decision_metric(
            decision=existing_decision or decision,
            status="idempotent",
            duration_seconds=perf_counter() - activity_start_time,
        )
        set_span_attributes(
            {
                "approval_id": approval_id,
                "approval.decision": existing_decision,
                "idempotent": True,
            }
        )
        return {
            "workflow_id": workflow_id,
            "approval_id": approval_id,
            "decision": existing_decision,
            "idempotent": True,
        }

    await publish_workflow_event(event_id)
    logger.info(
        "approval decision recorded",
        extra={
            "workflow_id": workflow_id,
            "correlation_id": correlation_id,
            "approval_id": approval_id,
            "decision": decision,
            "status": "recorded",
        },
    )
    record_approval_decision_metric(
        decision=decision,
        status="recorded",
        duration_seconds=perf_counter() - activity_start_time,
    )
    set_span_attributes(
        {
            "approval_id": approval_id,
            "approval.decision": decision,
            "reviewed_by": reviewed_by,
            "idempotent": False,
        }
    )
    return {
        "workflow_id": workflow_id,
        "approval_id": approval_id,
        "decision": decision,
        "idempotent": False,
    }


def _validate_payload(*, decision: str, reviewed_by: str, comment: str | None) -> None:
    if decision not in TERMINAL_DECISIONS:
        raise ApplicationError("Approval decision must be APPROVED or REJECTED", non_retryable=True)
    if not reviewed_by.strip():
        raise ApplicationError("Approval decision requires reviewed_by", non_retryable=True)
    if comment is None or not comment.strip():
        raise ApplicationError("Approval decision requires a comment", non_retryable=True)


def _coerce_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    raise ApplicationError("Invalid datetime value for approval decision", non_retryable=True)
