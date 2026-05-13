import logging
from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID, uuid4

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from sqlalchemy import func, select
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
from aegisflow_gateway.services.evidence import WorkflowEvidenceReconstructor, WorkflowEvidenceSnapshot
from aegisflow_gateway.services.events import WorkflowEventPublisher
from aegisflow_gateway.services.outbox_recovery import OutboxEventClassification, OutboxRecoveryService
from aegisflow_gateway.services.replay import (
    DeterministicReplayValidationResult,
    DeterministicReplayValidator,
    build_history_reconstruction_steps,
    replay_run_status_for_steps,
)
from aegisflow_gateway.services.workflow_recovery import WorkflowRecoveryCheck, WorkflowRecoveryPlanner
from aegisflow_gateway.telemetry.metrics import (
    record_outbox_event_status_counts,
    record_outbox_retry,
    record_recovery_action,
    record_replay_run,
    record_replay_step,
    record_stuck_workflow_diagnostic,
)

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


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

    async def create_orchestrated_replay_run(
        self,
        workflow_id: UUID,
        *,
        replay_mode: ReplayMode,
        requested_by: str,
        correlation_id: str | None = None,
        replay_run_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> WorkflowReplayRun:
        start_time = perf_counter()
        status_value = ReplayRunStatus.failed.value
        with tracer.start_as_current_span("gateway.replay.run.create") as span:
            span.set_attribute("workflow_id", str(workflow_id))
            span.set_attribute("replay.mode", replay_mode.value)
            span.set_attribute("replay.side_effect_free", True)
            if correlation_id:
                span.set_attribute("correlation_id", correlation_id)
            logger.info(
                "replay run started",
                extra={
                    "workflow_id": str(workflow_id),
                    "correlation_id": correlation_id,
                    "replay_mode": replay_mode.value,
                    "operation": "replay_run_create",
                    "status": "started",
                },
            )
            try:
                workflow = await self.get_workflow(workflow_id)
                span.set_attribute("workflow.type", workflow.workflow_type)
                span.set_attribute("workflow.state", workflow.state)
                if replay_mode not in {ReplayMode.history_reconstruction, ReplayMode.deterministic_validation}:
                    raise WorkflowReviewActionError(
                        error="unsupported_replay_mode",
                        message=f"Replay mode {replay_mode.value} is not supported by local replay orchestration",
                        status_code=400,
                    )

                if replay_run_id is not None:
                    existing = await self._get_existing_replay_run_for_idempotency(
                        replay_run_id=replay_run_id,
                        workflow_id=workflow_id,
                        replay_mode=replay_mode,
                    )
                    if existing is not None:
                        span.set_attribute("replay.idempotent_existing", True)
                        status_value = existing.status
                        record_replay_run(
                            replay_mode=replay_mode.value,
                            status=status_value,
                            duration_seconds=perf_counter() - start_time,
                        )
                        logger.info(
                            "replay run completed",
                            extra={
                                "workflow_id": str(workflow_id),
                                "correlation_id": existing.correlation_id,
                                "replay_run_id": existing.replay_run_id,
                                "replay_mode": existing.replay_mode,
                                "operation": "replay_run_create",
                                "status": existing.status,
                                "idempotent_existing": True,
                            },
                        )
                        return existing

                with tracer.start_as_current_span("gateway.replay.workflow_evidence.load") as evidence_span:
                    snapshot = await WorkflowEvidenceReconstructor(self.session).reconstruct(workflow)
                    evidence_span.set_attribute("workflow_id", str(workflow_id))
                    evidence_span.set_attribute("workflow.state", snapshot.workflow_state)
                    evidence_span.set_attribute("replay.artifact_count", len(snapshot.artifacts))
                    evidence_span.set_attribute("replay.diagnostic_count", len(snapshot.diagnostics))

                with tracer.start_as_current_span("gateway.replay.steps.validate") as validation_span:
                    validation_span.set_attribute("workflow_id", str(workflow_id))
                    validation_span.set_attribute("replay.mode", replay_mode.value)
                    if replay_mode == ReplayMode.history_reconstruction:
                        steps = build_history_reconstruction_steps(snapshot)
                        summary = (
                            f"History reconstruction created {len(steps)} replay steps from "
                            f"{len(snapshot.artifacts)} evidence artifacts and {len(snapshot.diagnostics)} diagnostics."
                        )
                    else:
                        validation = DeterministicReplayValidator().validate(snapshot)
                        steps = validation.steps
                        summary = validation.summary
                    validation_span.set_attribute("replay.step_count", len(steps))

                status = replay_run_status_for_steps(steps)
                status_value = status.value
                step_counts: dict[str, int] = {}
                for step in steps:
                    step_counts[step.status.value] = step_counts.get(step.status.value, 0) + 1

                with tracer.start_as_current_span("gateway.replay.run.persist") as persist_span:
                    now = datetime.now(timezone.utc)
                    replay_run = WorkflowReplayRun(
                        replay_run_id=str(replay_run_id or uuid4()),
                        workflow_id=str(workflow_id),
                        correlation_id=correlation_id or workflow.correlation_id,
                        replay_mode=replay_mode.value,
                        status=status.value,
                        source_temporal_workflow_id=workflow.temporal_workflow_id,
                        source_temporal_run_id=workflow.temporal_run_id,
                        started_at=now,
                        completed_at=now,
                        requested_by=requested_by,
                        replay_metadata={
                            **(metadata or {}),
                            "boundary": "side_effect_free",
                            "summary": summary,
                            "workflow_state": snapshot.workflow_state,
                            "artifact_counts": snapshot.artifact_counts,
                            "diagnostic_codes": [diagnostic.code for diagnostic in snapshot.diagnostics],
                            "step_counts": step_counts,
                            "sensitive_payloads_persisted": False,
                        },
                    )
                    self.session.add(replay_run)
                    await self.session.flush()
                    self.session.add_all(
                        [
                            WorkflowReplayStep(
                                replay_run_id=replay_run.replay_run_id,
                                workflow_id=replay_run.workflow_id,
                                sequence_number=step.sequence_number,
                                artifact_type=step.artifact_type,
                                artifact_id=step.artifact_id,
                                expected_state=step.expected_state,
                                observed_state=step.observed_state,
                                status=step.status.value,
                                message=step.message,
                                step_metadata=step.metadata,
                            )
                            for step in steps
                        ]
                    )
                    await self.session.commit()
                    await self.session.refresh(replay_run)
                    persist_span.set_attribute("replay.run_id", replay_run.replay_run_id)
                    persist_span.set_attribute("replay.status", replay_run.status)

                record_replay_run(
                    replay_mode=replay_mode.value,
                    status=status_value,
                    duration_seconds=perf_counter() - start_time,
                )
                for step in steps:
                    record_replay_step(artifact_type=step.artifact_type, status=step.status.value)

                mismatch_counts = {
                    step_status: count
                    for step_status, count in step_counts.items()
                    if step_status in {ReplayStepStatus.warn.value, ReplayStepStatus.fail.value}
                }
                if mismatch_counts:
                    logger.warning(
                        "replay mismatch detected",
                        extra={
                            "workflow_id": str(workflow_id),
                            "correlation_id": replay_run.correlation_id,
                            "replay_run_id": replay_run.replay_run_id,
                            "replay_mode": replay_run.replay_mode,
                            "operation": "replay_step_validation",
                            "status": replay_run.status,
                            "mismatch_counts": mismatch_counts,
                        },
                    )
                logger.info(
                    "replay run completed",
                    extra={
                        "workflow_id": str(workflow_id),
                        "correlation_id": replay_run.correlation_id,
                        "replay_run_id": replay_run.replay_run_id,
                        "replay_mode": replay_run.replay_mode,
                        "operation": "replay_run_create",
                        "status": replay_run.status,
                        "step_count": len(steps),
                    },
                )
                return replay_run
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                record_replay_run(
                    replay_mode=replay_mode.value,
                    status=status_value,
                    duration_seconds=perf_counter() - start_time,
                )
                logger.exception(
                    "replay run failed",
                    extra={
                        "workflow_id": str(workflow_id),
                        "correlation_id": correlation_id,
                        "replay_mode": replay_mode.value,
                        "operation": "replay_run_create",
                        "status": status_value,
                    },
                )
                raise

    async def _get_existing_replay_run_for_idempotency(
        self,
        *,
        replay_run_id: UUID,
        workflow_id: UUID,
        replay_mode: ReplayMode,
    ) -> WorkflowReplayRun | None:
        result = await self.session.execute(
            select(WorkflowReplayRun).where(WorkflowReplayRun.replay_run_id == str(replay_run_id))
        )
        replay_run = result.scalar_one_or_none()
        if replay_run is None:
            return None
        if replay_run.workflow_id != str(workflow_id) or replay_run.replay_mode != replay_mode.value:
            raise WorkflowReviewActionError(
                error="replay_run_id_conflict",
                message=f"Replay run {replay_run_id} already exists for a different workflow or mode",
                status_code=409,
            )
        return replay_run

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

    async def get_outbox_event(self, event_id: str) -> WorkflowEventOutbox:
        result = await self.session.execute(
            select(WorkflowEventOutbox).where(WorkflowEventOutbox.event_id == event_id)
        )
        event = result.scalar_one_or_none()
        if event is None:
            raise WorkflowReviewActionError(
                error="outbox_event_not_found",
                message=f"Outbox event {event_id} was not found",
                status_code=404,
            )
        return event

    async def classify_outbox_event(self, event_id: str) -> OutboxEventClassification:
        event = await self.get_outbox_event(event_id)
        classification = OutboxRecoveryService(self.session).classify(event)
        await self._record_outbox_publish_status_counts()
        return classification

    async def list_outbox_event_classifications(self, workflow_id: UUID) -> list[OutboxEventClassification]:
        await self.get_workflow(workflow_id)
        result = await self.session.execute(
            select(WorkflowEventOutbox)
            .where(WorkflowEventOutbox.workflow_id == str(workflow_id))
            .order_by(WorkflowEventOutbox.created_at.asc(), WorkflowEventOutbox.event_id.asc())
        )
        recovery_service = OutboxRecoveryService(self.session)
        classifications = [recovery_service.classify(event) for event in result.scalars().all()]
        await self._record_outbox_publish_status_counts()
        return classifications

    async def retry_outbox_event(
        self,
        event_id: str,
        *,
        requested_by: str,
        reason: str,
        publisher: WorkflowEventPublisher | None = None,
    ) -> WorkflowRecoveryAction:
        start_time = perf_counter()
        action_type = RecoveryActionType.retry_outbox_event.value
        status_value = RecoveryActionStatus.rejected.value
        event_type = "unknown"
        with tracer.start_as_current_span("gateway.recovery.outbox.retry") as span:
            span.set_attribute("outbox.event_id", event_id)
            span.set_attribute("recovery.action_type", action_type)
            logger.info(
                "recovery action requested",
                extra={
                    "operation": "recovery_action_execute",
                    "action_type": action_type,
                    "target_resource_type": "workflow_event_outbox",
                    "target_resource_id": event_id,
                    "status": "started",
                    "reason_present": bool(reason.strip()),
                },
            )
            try:
                event = await self.get_outbox_event(event_id)
                event_type = event.event_type
                span.set_attribute("workflow_id", event.workflow_id)
                span.set_attribute("correlation_id", event.correlation_id)
                span.set_attribute("event.type", event.event_type)
                span.set_attribute("outbox.publish_status", event.publish_status)
                action = await OutboxRecoveryService(self.session).retry_event(
                    event,
                    requested_by=requested_by,
                    reason=reason,
                    publisher=publisher,
                )
                status_value = action.status
                await self._record_outbox_publish_status_counts()
                record_recovery_action(
                    action_type=action_type,
                    status=status_value,
                    duration_seconds=perf_counter() - start_time,
                )
                record_outbox_retry(event_type=event_type, status=status_value)
                logger.info(
                    "outbox event retried",
                    extra={
                        "workflow_id": event.workflow_id,
                        "correlation_id": event.correlation_id,
                        "recovery_action_id": action.recovery_action_id,
                        "action_type": action.action_type,
                        "target_resource_type": action.target_resource_type,
                        "target_resource_id": action.target_resource_id,
                        "event_type": event.event_type,
                        "operation": "outbox_event_retry",
                        "status": action.status,
                        "final_publish_status": event.publish_status,
                    },
                )
                return action
            except ValueError as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                record_recovery_action(
                    action_type=action_type,
                    status=status_value,
                    duration_seconds=perf_counter() - start_time,
                )
                record_outbox_retry(event_type=event_type, status=status_value)
                logger.warning(
                    "recovery action failed",
                    extra={
                        "operation": "outbox_event_retry",
                        "action_type": action_type,
                        "target_resource_type": "workflow_event_outbox",
                        "target_resource_id": event_id,
                        "event_type": event_type,
                        "status": status_value,
                        "error": "outbox_event_not_retryable",
                    },
                )
                raise WorkflowReviewActionError(
                    error="outbox_event_not_retryable",
                    message=str(exc),
                    status_code=409,
                ) from exc
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                record_recovery_action(
                    action_type=action_type,
                    status=status_value,
                    duration_seconds=perf_counter() - start_time,
                )
                record_outbox_retry(event_type=event_type, status=status_value)
                logger.warning(
                    "recovery action failed",
                    extra={
                        "operation": "outbox_event_retry",
                        "action_type": action_type,
                        "target_resource_type": "workflow_event_outbox",
                        "target_resource_id": event_id,
                        "event_type": event_type,
                        "status": status_value,
                    },
                )
                raise

    async def mark_outbox_event_dead_lettered(
        self,
        event_id: str,
        *,
        requested_by: str,
        reason: str,
    ) -> WorkflowRecoveryAction:
        start_time = perf_counter()
        action_type = RecoveryActionType.mark_outbox_event_dead_lettered.value
        status_value = RecoveryActionStatus.rejected.value
        with tracer.start_as_current_span("gateway.recovery.outbox.dead_letter") as span:
            span.set_attribute("outbox.event_id", event_id)
            span.set_attribute("recovery.action_type", action_type)
            logger.info(
                "recovery action requested",
                extra={
                    "operation": "recovery_action_execute",
                    "action_type": action_type,
                    "target_resource_type": "workflow_event_outbox",
                    "target_resource_id": event_id,
                    "status": "started",
                    "reason_present": bool(reason.strip()),
                },
            )
            try:
                event = await self.get_outbox_event(event_id)
                span.set_attribute("workflow_id", event.workflow_id)
                span.set_attribute("correlation_id", event.correlation_id)
                span.set_attribute("event.type", event.event_type)
                span.set_attribute("outbox.publish_status", event.publish_status)
                action = await OutboxRecoveryService(self.session).mark_dead_lettered(
                    event,
                    requested_by=requested_by,
                    reason=reason,
                )
                status_value = action.status
                await self._record_outbox_publish_status_counts()
                record_recovery_action(
                    action_type=action_type,
                    status=status_value,
                    duration_seconds=perf_counter() - start_time,
                )
                logger.info(
                    "outbox event dead-lettered",
                    extra={
                        "workflow_id": event.workflow_id,
                        "correlation_id": event.correlation_id,
                        "recovery_action_id": action.recovery_action_id,
                        "action_type": action.action_type,
                        "target_resource_type": action.target_resource_type,
                        "target_resource_id": action.target_resource_id,
                        "event_type": event.event_type,
                        "operation": "outbox_event_dead_letter",
                        "status": action.status,
                        "final_publish_status": event.publish_status,
                    },
                )
                return action
            except ValueError as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                record_recovery_action(
                    action_type=action_type,
                    status=status_value,
                    duration_seconds=perf_counter() - start_time,
                )
                logger.warning(
                    "recovery action failed",
                    extra={
                        "operation": "outbox_event_dead_letter",
                        "action_type": action_type,
                        "target_resource_type": "workflow_event_outbox",
                        "target_resource_id": event_id,
                        "status": status_value,
                        "error": "outbox_event_not_dead_letterable",
                    },
                )
                raise WorkflowReviewActionError(
                    error="outbox_event_not_dead_letterable",
                    message=str(exc),
                    status_code=409,
                ) from exc
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                record_recovery_action(
                    action_type=action_type,
                    status=status_value,
                    duration_seconds=perf_counter() - start_time,
                )
                logger.warning(
                    "recovery action failed",
                    extra={
                        "operation": "outbox_event_dead_letter",
                        "action_type": action_type,
                        "target_resource_type": "workflow_event_outbox",
                        "target_resource_id": event_id,
                        "status": status_value,
                    },
                )
                raise

    async def check_workflow_recovery(
        self,
        workflow_id: UUID,
        *,
        action_type: RecoveryActionType,
    ) -> WorkflowRecoveryCheck:
        workflow = await self.get_workflow(workflow_id)
        with tracer.start_as_current_span("gateway.recovery.workflow.check") as span:
            span.set_attribute("workflow_id", str(workflow_id))
            span.set_attribute("workflow.type", workflow.workflow_type)
            span.set_attribute("workflow.state", workflow.state)
            span.set_attribute("recovery.action_type", action_type.value)
            check = await WorkflowRecoveryPlanner(self.session).check(workflow, action_type=action_type)
            span.set_attribute("recovery.allowed", check.allowed)
            if action_type == RecoveryActionType.resume_stuck_workflow_check:
                record_stuck_workflow_diagnostic(
                    workflow_type=workflow.workflow_type,
                    diagnostic_status="allowed" if check.allowed else "rejected",
                )
            return check

    async def request_workflow_recovery(
        self,
        workflow_id: UUID,
        *,
        action_type: RecoveryActionType,
        requested_by: str,
        reason: str,
        correlation_id: str | None = None,
        recovery_action_id: UUID | None = None,
    ) -> WorkflowRecoveryAction:
        start_time = perf_counter()
        status_value = RecoveryActionStatus.rejected.value
        with tracer.start_as_current_span("gateway.recovery.workflow.request") as span:
            span.set_attribute("workflow_id", str(workflow_id))
            span.set_attribute("recovery.action_type", action_type.value)
            if correlation_id:
                span.set_attribute("correlation_id", correlation_id)
            logger.info(
                "recovery action requested",
                extra={
                    "workflow_id": str(workflow_id),
                    "correlation_id": correlation_id,
                    "operation": "workflow_recovery_request",
                    "action_type": action_type.value,
                    "status": "started",
                    "reason_present": bool(reason.strip()),
                },
            )
            try:
                if not requested_by.strip():
                    raise WorkflowReviewActionError(
                        error="recovery_actor_required",
                        message="Workflow recovery commands require a local actor identity",
                        status_code=400,
                    )
                if not reason.strip():
                    raise WorkflowReviewActionError(
                        error="recovery_reason_required",
                        message="Workflow recovery commands require a reason",
                        status_code=400,
                    )

                workflow = await self.get_workflow(workflow_id)
                span.set_attribute("workflow.type", workflow.workflow_type)
                span.set_attribute("workflow.state", workflow.state)
                check = await WorkflowRecoveryPlanner(self.session).check(workflow, action_type=action_type)
                span.set_attribute("recovery.allowed", check.allowed)
                if not check.allowed:
                    raise WorkflowReviewActionError(
                        error="workflow_recovery_not_allowed",
                        message=check.reason,
                        status_code=409,
                    )
                if not check.requires_engine_execution:
                    raise WorkflowReviewActionError(
                        error="workflow_recovery_dry_run_only",
                        message=f"Recovery action {action_type.value} is a dry-run check and does not create a mutation request",
                        status_code=400,
                    )

                recovery_action = WorkflowRecoveryAction(
                    recovery_action_id=str(recovery_action_id or uuid4()),
                    workflow_id=str(workflow_id),
                    correlation_id=correlation_id or workflow.correlation_id,
                    action_type=action_type.value,
                    target_resource_type=check.target_resource_type,
                    target_resource_id=check.target_resource_id,
                    status=RecoveryActionStatus.requested.value,
                    requested_by=requested_by,
                    reason=reason,
                    result_metadata={
                        "dry_run_allowed": check.allowed,
                        "dry_run_reason": check.reason,
                        "current_state": check.current_state,
                        "proposed_state": check.proposed_state,
                        "requires_engine_execution": check.requires_engine_execution,
                        "engine_owned_mutation_required": True,
                        "check_metadata": check.metadata,
                        "sensitive_payloads_persisted": False,
                    },
                )
                self.session.add(recovery_action)
                await self.session.commit()
                await self.session.refresh(recovery_action)
                status_value = recovery_action.status
                record_recovery_action(
                    action_type=action_type.value,
                    status=status_value,
                    duration_seconds=perf_counter() - start_time,
                )
                logger.info(
                    "recovery action completed",
                    extra={
                        "workflow_id": str(workflow_id),
                        "correlation_id": recovery_action.correlation_id,
                        "recovery_action_id": recovery_action.recovery_action_id,
                        "operation": "workflow_recovery_request",
                        "action_type": recovery_action.action_type,
                        "status": recovery_action.status,
                    },
                )
                return recovery_action
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                record_recovery_action(
                    action_type=action_type.value,
                    status=status_value,
                    duration_seconds=perf_counter() - start_time,
                )
                logger.warning(
                    "recovery action failed",
                    extra={
                        "workflow_id": str(workflow_id),
                        "correlation_id": correlation_id,
                        "operation": "workflow_recovery_request",
                        "action_type": action_type.value,
                        "status": status_value,
                    },
                )
                raise

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

    async def _record_outbox_publish_status_counts(self) -> None:
        result = await self.session.execute(
            select(WorkflowEventOutbox.publish_status, func.count())
            .group_by(WorkflowEventOutbox.publish_status)
        )
        record_outbox_event_status_counts({status: count for status, count in result.all()})

    async def reconstruct_workflow_evidence(self, workflow_id: UUID) -> WorkflowEvidenceSnapshot:
        workflow = await self.get_workflow(workflow_id)
        with tracer.start_as_current_span("gateway.replay.workflow_evidence.load") as span:
            span.set_attribute("workflow_id", str(workflow_id))
            span.set_attribute("workflow.type", workflow.workflow_type)
            span.set_attribute("workflow.state", workflow.state)
            snapshot = await WorkflowEvidenceReconstructor(self.session).reconstruct(workflow)
            span.set_attribute("replay.artifact_count", len(snapshot.artifacts))
            span.set_attribute("replay.diagnostic_count", len(snapshot.diagnostics))
            return snapshot

    async def validate_deterministic_replay(self, workflow_id: UUID) -> DeterministicReplayValidationResult:
        with tracer.start_as_current_span("gateway.replay.diagnostics.validate") as span:
            snapshot = await self.reconstruct_workflow_evidence(workflow_id)
            validation = DeterministicReplayValidator().validate(snapshot)
            span.set_attribute("workflow_id", str(workflow_id))
            span.set_attribute("replay.status", validation.status.value)
            span.set_attribute("replay.step_count", len(validation.steps))
            logger.info(
                "replay diagnostics completed",
                extra={
                    "workflow_id": str(workflow_id),
                    "correlation_id": snapshot.correlation_id,
                    "operation": "replay_diagnostics",
                    "status": validation.status.value,
                    "step_count": len(validation.steps),
                },
            )
            return validation
