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
    ToolInvocationRecord,
    WorkflowEventOutbox,
    WorkflowRecord,
    WorkflowTimelineEntry,
)
from aegisflow_workflow_engine.metrics import record_tool_invocation as record_tool_invocation_metric
from aegisflow_workflow_engine.telemetry import instrument_activity, set_span_attributes

logger = logging.getLogger(__name__)


@activity.defn(name="record_tool_invocation")
@instrument_activity("record_tool_invocation")
async def record_tool_invocation(payload: dict) -> dict:
    workflow_id = payload["workflow_id"]
    correlation_id = payload["correlation_id"]
    tool_invocation_id = payload["tool_invocation_id"]
    tool_id = payload["tool_id"]
    status = payload["status"]
    activity_start_time = perf_counter()
    now = datetime.now(timezone.utc)
    started_at = _coerce_datetime(payload.get("started_at")) or now
    completed_at = _coerce_datetime(payload.get("completed_at")) or now

    existing_event_id: str | None = None
    existing_status: str | None = None
    async with SessionLocal() as session:
        result = await session.execute(
            select(WorkflowRecord).where(WorkflowRecord.workflow_id == workflow_id)
        )
        workflow = result.scalar_one_or_none()
        if workflow is None:
            raise ApplicationError(
                f"Workflow {workflow_id} was not found",
                non_retryable=True,
            )

        existing = await session.get(ToolInvocationRecord, tool_invocation_id)
        if existing is not None:
            existing_event_id = f"{workflow_id}:{_event_type_for_status(existing.status)}:{tool_invocation_id}"
            existing_status = existing.status
        if existing_event_id is not None:
            await session.commit()
        else:
            event_type = _event_type_for_status(status)
            timeline_entry_type = _timeline_entry_type_for_status(status)
            event_id = f"{workflow_id}:{event_type}:{tool_invocation_id}"

            session.add(
                ToolInvocationRecord(
                    tool_invocation_id=tool_invocation_id,
                    workflow_id=workflow_id,
                    correlation_id=correlation_id,
                    agent_execution_id=payload.get("agent_execution_id"),
                    agent_id=payload["agent_id"],
                    tool_id=tool_id,
                    status=status,
                    permission_status=payload["permission_status"],
                    input_validation_status=payload["input_validation_status"],
                    output_validation_status=payload["output_validation_status"],
                    input_metadata=payload.get("input_metadata", {}),
                    output_payload=payload.get("output_payload", {}),
                    execution_metadata=payload.get("execution_metadata", {}),
                    error_message=payload.get("error_message"),
                    created_by="workflow-engine",
                    started_at=started_at,
                    completed_at=completed_at,
                    created_at=now,
                )
            )

            session.add(
                WorkflowTimelineEntry(
                    timeline_entry_id=str(uuid4()),
                    workflow_id=workflow_id,
                    entry_type=timeline_entry_type,
                    message=f"Tool invocation {status.lower()}: {tool_id}",
                    state=workflow.state,
                    correlation_id=correlation_id,
                    created_by="workflow-engine",
                    entry_metadata={
                        "tool_invocation_id": tool_invocation_id,
                        "agent_execution_id": payload.get("agent_execution_id"),
                        "agent_id": payload["agent_id"],
                        "tool_id": tool_id,
                        "status": status,
                        "permission_status": payload["permission_status"],
                        "input_validation_status": payload["input_validation_status"],
                        "output_validation_status": payload["output_validation_status"],
                        "data_classification": payload.get("execution_metadata", {}).get("data_classification"),
                        "replay_safe": payload.get("execution_metadata", {}).get("replay_safe"),
                    },
                    created_at=completed_at,
                )
            )

            existing_event = await session.get(WorkflowEventOutbox, event_id)
            if existing_event is None:
                session.add(
                    WorkflowEventOutbox(
                        event_id=event_id,
                        event_type=event_type,
                        event_version="1",
                        workflow_id=workflow_id,
                        correlation_id=correlation_id,
                        payload={
                            "workflow_id": workflow_id,
                            "correlation_id": correlation_id,
                            "tool_invocation_id": tool_invocation_id,
                            "agent_execution_id": payload.get("agent_execution_id"),
                            "agent_id": payload["agent_id"],
                            "tool_id": tool_id,
                            "status": status,
                            "permission_status": payload["permission_status"],
                            "input_validation_status": payload["input_validation_status"],
                            "output_validation_status": payload["output_validation_status"],
                        },
                        publish_status=OutboxPublishStatus.pending.value,
                        retry_count=0,
                        last_error=None,
                        created_at=completed_at,
                        published_at=None,
                    )
                )

            await session.commit()

    if existing_event_id is not None:
        await publish_workflow_event(existing_event_id)
        record_tool_invocation_metric(
            tool_id=tool_id,
            status="idempotent",
            permission_status=payload.get("permission_status", "UNKNOWN"),
            duration_seconds=perf_counter() - activity_start_time,
        )
        set_span_attributes(
            {
                "tool_invocation_id": tool_invocation_id,
                "tool.status": existing_status,
                "tool.permission_status": payload.get("permission_status"),
                "idempotent": True,
            }
        )
        return {
            "workflow_id": workflow_id,
            "tool_invocation_id": tool_invocation_id,
            "tool_id": tool_id,
            "status": existing_status,
            "idempotent": True,
        }

    await publish_workflow_event(event_id)
    logger.info(
        "tool invocation recorded",
        extra={
            "workflow_id": workflow_id,
            "correlation_id": correlation_id,
            "tool_id": tool_id,
            "status": status,
            "permission_status": payload["permission_status"],
        },
    )
    record_tool_invocation_metric(
        tool_id=tool_id,
        status=status,
        permission_status=payload["permission_status"],
        duration_seconds=perf_counter() - activity_start_time,
    )
    set_span_attributes(
        {
            "tool_invocation_id": tool_invocation_id,
            "tool.status": status,
            "tool.permission_status": payload["permission_status"],
            "tool.input_validation_status": payload["input_validation_status"],
            "tool.output_validation_status": payload["output_validation_status"],
            "idempotent": False,
        }
    )
    return {
        "workflow_id": workflow_id,
        "tool_invocation_id": tool_invocation_id,
        "tool_id": tool_id,
        "status": status,
        "idempotent": False,
    }


def _event_type_for_status(status: str) -> str:
    if status == "COMPLETED":
        return WorkflowEventType.tool_invocation_completed.value
    return WorkflowEventType.tool_invocation_failed.value


def _timeline_entry_type_for_status(status: str) -> str:
    if status == "COMPLETED":
        return TimelineEntryType.tool_invocation_completed.value
    return TimelineEntryType.tool_invocation_failed.value


def _coerce_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    raise ApplicationError("Invalid datetime value for tool invocation", non_retryable=True)
