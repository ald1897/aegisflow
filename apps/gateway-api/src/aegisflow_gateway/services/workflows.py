from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegisflow_gateway.api.schemas import WorkflowCreateRequest
from aegisflow_gateway.domain.workflows import (
    OutboxPublishStatus,
    TimelineEntryType,
    WorkflowEventType,
    RecoveryActionStatus,
    RecoveryActionType,
    ReplayMode,
    ReplayRunStatus,
    ReplayStepStatus,
    WorkflowState,
)
from aegisflow_gateway.persistence.models import (
    AgentExecutionRecord,
    ApprovalRecord,
    EvaluationResult,
    EvaluationRun,
    ToolInvocationRecord,
    WorkflowRecoveryAction,
    WorkflowEventOutbox,
    WorkflowRecord,
    WorkflowReplayRun,
    WorkflowReplayStep,
    WorkflowStateTransition,
    WorkflowTimelineEntry,
)


class WorkflowNotFoundError(Exception):
    def __init__(self, workflow_id: UUID) -> None:
        self.workflow_id = workflow_id
        super().__init__(f"Workflow {workflow_id} was not found")


class WorkflowReviewActionError(Exception):
    def __init__(self, *, error: str, message: str, status_code: int) -> None:
        self.error = error
        self.message = message
        self.status_code = status_code
        super().__init__(message)


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

    async def list_tool_invocations(self, workflow_id: UUID) -> list[ToolInvocationRecord]:
        await self.get_workflow(workflow_id)
        result = await self.session.execute(
            select(ToolInvocationRecord)
            .where(ToolInvocationRecord.workflow_id == str(workflow_id))
            .order_by(ToolInvocationRecord.created_at.asc(), ToolInvocationRecord.tool_invocation_id.asc())
        )
        return list(result.scalars().all())

    async def list_human_review_queue(self) -> list[WorkflowRecord]:
        result = await self.session.execute(
            select(WorkflowRecord)
            .where(WorkflowRecord.state == WorkflowState.human_review_required.value)
            .order_by(WorkflowRecord.updated_at.asc(), WorkflowRecord.workflow_id.asc())
        )
        return list(result.scalars().all())

    async def list_approval_records(self, workflow_id: UUID) -> list[ApprovalRecord]:
        await self.get_workflow(workflow_id)
        result = await self.session.execute(
            select(ApprovalRecord)
            .where(ApprovalRecord.workflow_id == str(workflow_id))
            .order_by(ApprovalRecord.reviewed_at.asc(), ApprovalRecord.approval_id.asc())
        )
        return list(result.scalars().all())

    async def require_human_reviewable_workflow(self, workflow_id: UUID) -> WorkflowRecord:
        workflow = await self.get_workflow(workflow_id)
        if workflow.state != WorkflowState.human_review_required.value:
            raise WorkflowReviewActionError(
                error="workflow_not_reviewable",
                message=f"Workflow {workflow_id} is not in HUMAN_REVIEW_REQUIRED state",
                status_code=409,
            )
        return workflow

    async def list_evaluation_runs(self, workflow_id: UUID) -> list[EvaluationRun]:
        await self.get_workflow(workflow_id)
        result = await self.session.execute(
            select(EvaluationRun)
            .where(EvaluationRun.workflow_id == str(workflow_id))
            .order_by(EvaluationRun.started_at.asc(), EvaluationRun.evaluation_run_id.asc())
        )
        return list(result.scalars().all())

    async def list_evaluation_results(self, evaluation_run_id: UUID | str) -> list[EvaluationResult]:
        result = await self.session.execute(
            select(EvaluationResult)
            .where(EvaluationResult.evaluation_run_id == str(evaluation_run_id))
            .order_by(EvaluationResult.created_at.asc(), EvaluationResult.evaluation_result_id.asc())
        )
        return list(result.scalars().all())

    async def create_replay_run(
        self,
        workflow_id: UUID,
        *,
        replay_mode: ReplayMode,
        requested_by: str,
        correlation_id: str | None = None,
        replay_run_id: UUID | None = None,
        status: ReplayRunStatus = ReplayRunStatus.requested,
        metadata: dict | None = None,
    ) -> WorkflowReplayRun:
        workflow = await self.get_workflow(workflow_id)
        replay_run = WorkflowReplayRun(
            replay_run_id=str(replay_run_id or uuid4()),
            workflow_id=str(workflow_id),
            correlation_id=correlation_id or workflow.correlation_id,
            replay_mode=replay_mode.value,
            status=status.value,
            source_temporal_workflow_id=workflow.temporal_workflow_id,
            source_temporal_run_id=workflow.temporal_run_id,
            requested_by=requested_by,
            replay_metadata=metadata or {},
        )
        self.session.add(replay_run)
        await self.session.commit()
        await self.session.refresh(replay_run)
        return replay_run

    async def get_replay_run(self, replay_run_id: UUID) -> WorkflowReplayRun:
        result = await self.session.execute(
            select(WorkflowReplayRun).where(WorkflowReplayRun.replay_run_id == str(replay_run_id))
        )
        replay_run = result.scalar_one_or_none()
        if replay_run is None:
            raise WorkflowReviewActionError(
                error="replay_run_not_found",
                message=f"Replay run {replay_run_id} was not found",
                status_code=404,
            )
        return replay_run

    async def list_replay_runs(self, workflow_id: UUID) -> list[WorkflowReplayRun]:
        await self.get_workflow(workflow_id)
        result = await self.session.execute(
            select(WorkflowReplayRun)
            .where(WorkflowReplayRun.workflow_id == str(workflow_id))
            .order_by(WorkflowReplayRun.started_at.asc(), WorkflowReplayRun.replay_run_id.asc())
        )
        return list(result.scalars().all())

    async def create_replay_step(
        self,
        replay_run_id: UUID,
        *,
        sequence_number: int,
        artifact_type: str,
        status: ReplayStepStatus,
        message: str,
        artifact_id: str | None = None,
        expected_state: str | None = None,
        observed_state: str | None = None,
        metadata: dict | None = None,
        replay_step_id: UUID | None = None,
    ) -> WorkflowReplayStep:
        replay_run = await self.get_replay_run(replay_run_id)
        replay_step = WorkflowReplayStep(
            replay_step_id=str(replay_step_id or uuid4()),
            replay_run_id=str(replay_run_id),
            workflow_id=replay_run.workflow_id,
            sequence_number=sequence_number,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            expected_state=expected_state,
            observed_state=observed_state,
            status=status.value,
            message=message,
            step_metadata=metadata or {},
        )
        self.session.add(replay_step)
        await self.session.commit()
        await self.session.refresh(replay_step)
        return replay_step

    async def list_replay_steps(self, replay_run_id: UUID) -> list[WorkflowReplayStep]:
        await self.get_replay_run(replay_run_id)
        result = await self.session.execute(
            select(WorkflowReplayStep)
            .where(WorkflowReplayStep.replay_run_id == str(replay_run_id))
            .order_by(WorkflowReplayStep.sequence_number.asc(), WorkflowReplayStep.replay_step_id.asc())
        )
        return list(result.scalars().all())

    async def create_recovery_action(
        self,
        workflow_id: UUID,
        *,
        action_type: RecoveryActionType,
        target_resource_type: str,
        target_resource_id: str,
        requested_by: str,
        reason: str,
        correlation_id: str | None = None,
        recovery_action_id: UUID | None = None,
        status: RecoveryActionStatus = RecoveryActionStatus.requested,
        metadata: dict | None = None,
    ) -> WorkflowRecoveryAction:
        workflow = await self.get_workflow(workflow_id)
        recovery_action = WorkflowRecoveryAction(
            recovery_action_id=str(recovery_action_id or uuid4()),
            workflow_id=str(workflow_id),
            correlation_id=correlation_id or workflow.correlation_id,
            action_type=action_type.value,
            target_resource_type=target_resource_type,
            target_resource_id=target_resource_id,
            status=status.value,
            requested_by=requested_by,
            reason=reason,
            result_metadata=metadata or {},
        )
        self.session.add(recovery_action)
        await self.session.commit()
        await self.session.refresh(recovery_action)
        return recovery_action

    async def get_recovery_action(self, recovery_action_id: UUID) -> WorkflowRecoveryAction:
        result = await self.session.execute(
            select(WorkflowRecoveryAction)
            .where(WorkflowRecoveryAction.recovery_action_id == str(recovery_action_id))
        )
        recovery_action = result.scalar_one_or_none()
        if recovery_action is None:
            raise WorkflowReviewActionError(
                error="recovery_action_not_found",
                message=f"Recovery action {recovery_action_id} was not found",
                status_code=404,
            )
        return recovery_action

    async def list_recovery_actions(self, workflow_id: UUID) -> list[WorkflowRecoveryAction]:
        await self.get_workflow(workflow_id)
        result = await self.session.execute(
            select(WorkflowRecoveryAction)
            .where(WorkflowRecoveryAction.workflow_id == str(workflow_id))
            .order_by(WorkflowRecoveryAction.started_at.asc(), WorkflowRecoveryAction.recovery_action_id.asc())
        )
        return list(result.scalars().all())
