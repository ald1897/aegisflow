from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegisflow_gateway.api.schemas import WorkflowCreateRequest
from aegisflow_gateway.domain.workflows import (
    OutboxPublishStatus,
    TimelineEntryType,
    WorkflowEventType,
    WorkflowState,
)
from aegisflow_gateway.persistence.models import (
    AgentExecutionRecord,
    WorkflowEventOutbox,
    WorkflowRecord,
    WorkflowStateTransition,
    WorkflowTimelineEntry,
)


class WorkflowNotFoundError(Exception):
    def __init__(self, workflow_id: UUID) -> None:
        self.workflow_id = workflow_id
        super().__init__(f"Workflow {workflow_id} was not found")


class WorkflowService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_workflow(
        self,
        request: WorkflowCreateRequest,
        *,
        correlation_id: str,
        actor_id: str,
    ) -> WorkflowRecord:
        workflow = WorkflowRecord(
            workflow_type=request.workflow_type.value,
            state=WorkflowState.new.value,
            priority=request.priority.value,
            correlation_id=correlation_id,
            created_by=actor_id,
            workflow_metadata=request.metadata,
        )
        self.session.add(workflow)
        await self.session.flush()

        transition = WorkflowStateTransition(
            workflow_id=workflow.workflow_id,
            prior_state=None,
            new_state=WorkflowState.new.value,
            transition_reason="workflow_created",
            correlation_id=correlation_id,
            created_by=actor_id,
        )
        self.session.add(transition)

        timeline_entry = WorkflowTimelineEntry(
            workflow_id=workflow.workflow_id,
            entry_type=TimelineEntryType.workflow_created.value,
            message="Workflow created",
            state=WorkflowState.new.value,
            correlation_id=correlation_id,
            created_by=actor_id,
            entry_metadata={"workflow_type": request.workflow_type.value},
        )
        self.session.add(timeline_entry)

        outbox_event = WorkflowEventOutbox(
            event_id=f"{workflow.workflow_id}:workflow.created",
            event_type=WorkflowEventType.created.value,
            event_version="1",
            workflow_id=workflow.workflow_id,
            correlation_id=correlation_id,
            payload={
                "workflow_id": workflow.workflow_id,
                "workflow_type": request.workflow_type.value,
                "state": WorkflowState.new.value,
                "priority": request.priority.value,
            },
            publish_status=OutboxPublishStatus.pending.value,
        )
        self.session.add(outbox_event)

        await self.session.commit()
        await self.session.refresh(workflow)
        return workflow

    async def get_workflow(self, workflow_id: UUID) -> WorkflowRecord:
        result = await self.session.execute(
            select(WorkflowRecord).where(WorkflowRecord.workflow_id == str(workflow_id))
        )
        workflow = result.scalar_one_or_none()
        if workflow is None:
            raise WorkflowNotFoundError(workflow_id)
        return workflow

    async def update_temporal_metadata(
        self,
        workflow_id: UUID,
        *,
        temporal_workflow_id: str,
        temporal_run_id: str,
    ) -> WorkflowRecord:
        workflow = await self.get_workflow(workflow_id)
        workflow.temporal_workflow_id = temporal_workflow_id
        workflow.temporal_run_id = temporal_run_id
        workflow.started_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(workflow)
        return workflow

    async def list_timeline_entries(self, workflow_id: UUID) -> list[WorkflowTimelineEntry]:
        await self.get_workflow(workflow_id)
        result = await self.session.execute(
            select(WorkflowTimelineEntry)
            .where(WorkflowTimelineEntry.workflow_id == str(workflow_id))
            .order_by(WorkflowTimelineEntry.created_at.asc(), WorkflowTimelineEntry.timeline_entry_id.asc())
        )
        return list(result.scalars().all())

    async def list_agent_executions(self, workflow_id: UUID) -> list[AgentExecutionRecord]:
        await self.get_workflow(workflow_id)
        result = await self.session.execute(
            select(AgentExecutionRecord)
            .where(AgentExecutionRecord.workflow_id == str(workflow_id))
            .order_by(AgentExecutionRecord.created_at.asc(), AgentExecutionRecord.agent_execution_id.asc())
        )
        return list(result.scalars().all())
