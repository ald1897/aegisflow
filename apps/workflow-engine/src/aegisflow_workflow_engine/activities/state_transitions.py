import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from aiokafka import AIOKafkaProducer
from sqlalchemy import select
from temporalio import activity
from temporalio.exceptions import ApplicationError

from aegisflow_workflow_engine.config import get_settings
from aegisflow_workflow_engine.domain import (
    OutboxPublishStatus,
    TimelineEntryType,
    WorkflowEventType,
    WorkflowState,
    is_valid_transition,
)
from aegisflow_workflow_engine.persistence.database import SessionLocal
from aegisflow_workflow_engine.persistence.models import (
    WorkflowEventOutbox,
    WorkflowRecord,
    WorkflowStateTransition,
    WorkflowTimelineEntry,
)

logger = logging.getLogger(__name__)


@activity.defn(name="advance_workflow_state")
async def advance_workflow_state(payload: dict) -> dict:
    workflow_id = payload["workflow_id"]
    correlation_id = payload["correlation_id"]
    target_state = WorkflowState(payload["target_state"])
    transition_reason = payload["transition_reason"]
    message = payload["message"]
    created_by = "workflow-engine"
    now = datetime.now(timezone.utc)

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

        prior_state = WorkflowState(workflow.state)
        if prior_state == target_state:
            return {"workflow_id": workflow_id, "state": target_state.value, "idempotent": True}

        if not is_valid_transition(prior_state, target_state):
            raise ApplicationError(
                f"Invalid workflow transition {prior_state.value} -> {target_state.value}",
                non_retryable=True,
            )

        workflow.state = target_state.value
        workflow.updated_at = now
        if target_state == WorkflowState.completed:
            workflow.completed_at = now
        if target_state == WorkflowState.failed:
            workflow.failed_at = now

        transition = WorkflowStateTransition(
            transition_id=str(uuid4()),
            workflow_id=workflow_id,
            prior_state=prior_state.value,
            new_state=target_state.value,
            transition_reason=transition_reason,
            correlation_id=correlation_id,
            created_by=created_by,
            created_at=now,
        )
        session.add(transition)

        timeline_entry = WorkflowTimelineEntry(
            timeline_entry_id=str(uuid4()),
            workflow_id=workflow_id,
            entry_type=TimelineEntryType.state_transition.value,
            message=message,
            state=target_state.value,
            correlation_id=correlation_id,
            created_by=created_by,
            entry_metadata={
                "prior_state": prior_state.value,
                "new_state": target_state.value,
                "transition_reason": transition_reason,
            },
            created_at=now,
        )
        session.add(timeline_entry)

        event_type = (
            WorkflowEventType.failed.value
            if target_state == WorkflowState.failed
            else WorkflowEventType.state_changed.value
        )
        event_id = f"{workflow_id}:{event_type}:{target_state.value}"
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
                        "prior_state": prior_state.value,
                        "new_state": target_state.value,
                        "transition_reason": transition_reason,
                    },
                    publish_status=OutboxPublishStatus.pending.value,
                    retry_count=0,
                    last_error=None,
                    created_at=now,
                    published_at=None,
                )
            )

        await session.commit()

    await publish_workflow_event(event_id)
    return {"workflow_id": workflow_id, "state": target_state.value, "idempotent": False}


async def publish_workflow_event(event_id: str) -> None:
    settings = get_settings()
    if not settings.enable_event_publishing:
        return

    async with SessionLocal() as session:
        event = await session.get(WorkflowEventOutbox, event_id)
        if event is None or event.publish_status == OutboxPublishStatus.published.value:
            return

        producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
        try:
            await producer.start()
            await producer.send_and_wait(
                settings.kafka_workflow_events_topic,
                key=event.workflow_id.encode("utf-8"),
                value=json.dumps(
                    {
                        "event_id": event.event_id,
                        "event_type": event.event_type,
                        "event_version": event.event_version,
                        "workflow_id": event.workflow_id,
                        "correlation_id": event.correlation_id,
                        "payload": event.payload,
                    },
                    default=str,
                ).encode("utf-8"),
            )
            event.publish_status = OutboxPublishStatus.published.value
            event.published_at = datetime.now(timezone.utc)
            event.last_error = None
            session.add(
                WorkflowTimelineEntry(
                    timeline_entry_id=str(uuid4()),
                    workflow_id=event.workflow_id,
                    entry_type=TimelineEntryType.event_published.value,
                    message=f"Workflow event published: {event.event_type}",
                    state=None,
                    correlation_id=event.correlation_id,
                    created_by="workflow-engine",
                    entry_metadata={"event_id": event.event_id, "event_type": event.event_type},
                    created_at=datetime.now(timezone.utc),
                )
            )
            logger.info("workflow event published", extra={"workflow_id": event.workflow_id})
        except Exception as exc:
            event.publish_status = OutboxPublishStatus.failed.value
            event.retry_count += 1
            event.last_error = str(exc)
            session.add(
                WorkflowTimelineEntry(
                    timeline_entry_id=str(uuid4()),
                    workflow_id=event.workflow_id,
                    entry_type=TimelineEntryType.event_publish_failed.value,
                    message=f"Workflow event publication failed: {event.event_type}",
                    state=None,
                    correlation_id=event.correlation_id,
                    created_by="workflow-engine",
                    entry_metadata={"event_id": event.event_id, "error": str(exc)},
                    created_at=datetime.now(timezone.utc),
                )
            )
            logger.exception("workflow event publication failed", extra={"workflow_id": event.workflow_id})
        finally:
            await producer.stop()

        await session.commit()
