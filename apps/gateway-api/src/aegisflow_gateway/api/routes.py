import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from aegisflow_gateway.api.schemas import (
    AgentExecutionRecordResponse,
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    ApprovalRecordResponse,
    EvaluationResultResponse,
    EvaluationRunSummaryResponse,
    HealthResponse,
    HumanReviewQueueItemResponse,
    HumanReviewQueueResponse,
    ReadyResponse,
    RecoveryActionCreateRequest,
    RecoveryActionResponse,
    ReplayDiagnosticResponse,
    ReplayDiagnosticStepResponse,
    ReplayRunCreateRequest,
    ReplayRunResponse,
    ReplayStepResponse,
    ToolInvocationRecordResponse,
    WorkflowApprovalsResponse,
    WorkflowAgentExecutionsResponse,
    WorkflowEvaluationsResponse,
    WorkflowRecoveryActionsResponse,
    WorkflowRecoveryCheckResponse,
    WorkflowCreateRequest,
    WorkflowReplayRunsResponse,
    WorkflowReviewContextResponse,
    WorkflowResponse,
    WorkflowToolInvocationsResponse,
    WorkflowTimelineEntryResponse,
    WorkflowTimelineResponse,
)
from aegisflow_gateway.config import Settings, get_settings
from aegisflow_gateway.domain.workflows import RecoveryActionType
from aegisflow_gateway.persistence.database import check_database, get_session
from aegisflow_gateway.persistence.models import (
    AgentExecutionRecord,
    ApprovalRecord,
    EvaluationResult,
    EvaluationRun,
    ToolInvocationRecord,
    WorkflowRecoveryAction,
    WorkflowRecord,
    WorkflowReplayRun,
    WorkflowReplayStep,
    WorkflowTimelineEntry,
)
from aegisflow_gateway.security import Permission, require_permission, require_permissions
from aegisflow_gateway.services.events import WorkflowEventPublisher
from aegisflow_gateway.services.replay import ReplayValidationStep
from aegisflow_gateway.services.temporal import TemporalWorkflowStarter
from aegisflow_gateway.services.workflows import WorkflowReviewActionError, WorkflowService
from aegisflow_gateway.services.workflow_recovery import WorkflowRecoveryCheck
from aegisflow_gateway.telemetry.metrics import record_workflow_creation, render_prometheus_metrics

router = APIRouter()
logger = logging.getLogger(__name__)


def workflow_to_response(workflow: WorkflowRecord) -> WorkflowResponse:
    return WorkflowResponse(
        workflow_id=UUID(workflow.workflow_id),
        workflow_type=workflow.workflow_type,
        state=workflow.state,
        priority=workflow.priority,
        correlation_id=workflow.correlation_id,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        temporal_workflow_id=workflow.temporal_workflow_id,
        temporal_run_id=workflow.temporal_run_id,
        started_at=workflow.started_at,
        completed_at=workflow.completed_at,
        failed_at=workflow.failed_at,
        metadata=workflow.workflow_metadata,
    )


def timeline_entry_to_response(entry: WorkflowTimelineEntry) -> WorkflowTimelineEntryResponse:
    return WorkflowTimelineEntryResponse(
        timeline_entry_id=UUID(entry.timeline_entry_id),
        workflow_id=UUID(entry.workflow_id),
        entry_type=entry.entry_type,
        message=entry.message,
        state=entry.state,
        correlation_id=entry.correlation_id,
        created_by=entry.created_by,
        created_at=entry.created_at,
        metadata=entry.entry_metadata,
    )


def agent_execution_to_response(execution: AgentExecutionRecord) -> AgentExecutionRecordResponse:
    return AgentExecutionRecordResponse(
        agent_execution_id=UUID(execution.agent_execution_id),
        workflow_id=UUID(execution.workflow_id),
        agent_id=execution.agent_id,
        prompt_id=execution.prompt_id,
        prompt_version=execution.prompt_version,
        model_name=execution.model_name,
        status=execution.status,
        validation_status=execution.validation_status,
        confidence_score=execution.confidence_score,
        requires_human_review=execution.requires_human_review,
        output=execution.output_payload,
        metadata=execution.execution_metadata,
        correlation_id=execution.correlation_id,
        created_by=execution.created_by,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        created_at=execution.created_at,
    )


def tool_invocation_to_response(invocation: ToolInvocationRecord) -> ToolInvocationRecordResponse:
    return ToolInvocationRecordResponse(
        tool_invocation_id=UUID(invocation.tool_invocation_id),
        workflow_id=UUID(invocation.workflow_id),
        agent_execution_id=UUID(invocation.agent_execution_id) if invocation.agent_execution_id else None,
        agent_id=invocation.agent_id,
        tool_id=invocation.tool_id,
        status=invocation.status,
        permission_status=invocation.permission_status,
        input_validation_status=invocation.input_validation_status,
        output_validation_status=invocation.output_validation_status,
        input_metadata=invocation.input_metadata,
        output=invocation.output_payload,
        metadata=invocation.execution_metadata,
        error_message=invocation.error_message,
        correlation_id=invocation.correlation_id,
        created_by=invocation.created_by,
        started_at=invocation.started_at,
        completed_at=invocation.completed_at,
        created_at=invocation.created_at,
    )


def approval_to_response(approval: ApprovalRecord) -> ApprovalRecordResponse:
    return ApprovalRecordResponse(
        approval_id=UUID(approval.approval_id),
        workflow_id=UUID(approval.workflow_id),
        decision=approval.decision,
        decision_reason=approval.decision_reason,
        comment=approval.comment,
        reviewed_by=approval.reviewed_by,
        reviewed_at=approval.reviewed_at,
        metadata=approval.approval_metadata,
        correlation_id=approval.correlation_id,
        created_at=approval.created_at,
    )


def evaluation_result_to_response(result: EvaluationResult) -> EvaluationResultResponse:
    return EvaluationResultResponse(
        evaluation_result_id=UUID(result.evaluation_result_id),
        evaluation_run_id=UUID(result.evaluation_run_id),
        workflow_id=UUID(result.workflow_id),
        agent_execution_id=UUID(result.agent_execution_id) if result.agent_execution_id else None,
        prompt_id=result.prompt_id,
        prompt_version=result.prompt_version,
        model_name=result.model_name,
        evaluator_id=result.evaluator_id,
        evaluator_version=result.evaluator_version,
        score_name=result.score_name,
        score_value=result.score_value,
        score_status=result.score_status,
        severity=result.severity,
        rationale=result.rationale,
        metadata=result.result_metadata,
        created_at=result.created_at,
    )


def evaluation_run_to_response(run: EvaluationRun, results: list[EvaluationResult]) -> EvaluationRunSummaryResponse:
    return EvaluationRunSummaryResponse(
        evaluation_run_id=UUID(run.evaluation_run_id),
        workflow_id=UUID(run.workflow_id),
        correlation_id=run.correlation_id,
        evaluation_scope=run.evaluation_scope,
        evaluation_mode=run.evaluation_mode,
        dataset_id=run.dataset_id,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_by=run.created_by,
        metadata=run.run_metadata,
        created_at=run.created_at,
        results=[evaluation_result_to_response(result) for result in results],
    )


def replay_step_to_response(step: WorkflowReplayStep) -> ReplayStepResponse:
    return ReplayStepResponse(
        replay_step_id=UUID(step.replay_step_id),
        replay_run_id=UUID(step.replay_run_id),
        workflow_id=UUID(step.workflow_id),
        sequence_number=step.sequence_number,
        artifact_type=step.artifact_type,
        artifact_id=step.artifact_id,
        expected_state=step.expected_state,
        observed_state=step.observed_state,
        status=step.status,
        message=step.message,
        metadata=step.step_metadata,
        created_at=step.created_at,
    )


async def replay_run_to_response(service: WorkflowService, run: WorkflowReplayRun) -> ReplayRunResponse:
    steps = await service.list_replay_steps(UUID(run.replay_run_id))
    return ReplayRunResponse(
        replay_run_id=UUID(run.replay_run_id),
        workflow_id=UUID(run.workflow_id),
        correlation_id=run.correlation_id,
        replay_mode=run.replay_mode,
        status=run.status,
        source_temporal_workflow_id=run.source_temporal_workflow_id,
        source_temporal_run_id=run.source_temporal_run_id,
        started_at=run.started_at,
        completed_at=run.completed_at,
        requested_by=run.requested_by,
        metadata=run.replay_metadata,
        created_at=run.created_at,
        steps=[replay_step_to_response(step) for step in steps],
    )


def replay_validation_step_to_response(step: ReplayValidationStep) -> ReplayDiagnosticStepResponse:
    return ReplayDiagnosticStepResponse(
        sequence_number=step.sequence_number,
        artifact_type=step.artifact_type,
        artifact_id=step.artifact_id,
        expected_state=step.expected_state,
        observed_state=step.observed_state,
        status=step.status,
        message=step.message,
        metadata=step.metadata,
    )


def recovery_action_to_response(action: WorkflowRecoveryAction) -> RecoveryActionResponse:
    return RecoveryActionResponse(
        recovery_action_id=UUID(action.recovery_action_id),
        workflow_id=UUID(action.workflow_id),
        correlation_id=action.correlation_id,
        action_type=action.action_type,
        target_resource_type=action.target_resource_type,
        target_resource_id=action.target_resource_id,
        status=action.status,
        requested_by=action.requested_by,
        reason=action.reason,
        started_at=action.started_at,
        completed_at=action.completed_at,
        metadata=action.result_metadata,
        created_at=action.created_at,
    )


def recovery_check_to_response(check: WorkflowRecoveryCheck) -> WorkflowRecoveryCheckResponse:
    return WorkflowRecoveryCheckResponse(
        workflow_id=UUID(check.workflow_id),
        action_type=check.action_type,
        target_resource_type=check.target_resource_type,
        target_resource_id=check.target_resource_id,
        allowed=check.allowed,
        current_state=check.current_state,
        proposed_state=check.proposed_state,
        reason=check.reason,
        requires_engine_execution=check.requires_engine_execution,
        metadata=check.metadata,
    )


def workflow_to_review_queue_item(workflow: WorkflowRecord) -> HumanReviewQueueItemResponse:
    return HumanReviewQueueItemResponse(
        workflow_id=UUID(workflow.workflow_id),
        workflow_type=workflow.workflow_type,
        state=workflow.state,
        priority=workflow.priority,
        correlation_id=workflow.correlation_id,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        metadata=workflow.workflow_metadata,
    )


def require_actor_id(actor_id: str | None, *, action_name: str) -> str:
    if actor_id is None or not actor_id.strip():
        raise WorkflowReviewActionError(
            error="actor_required",
            message=f"{action_name} requires X-Actor-ID",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return actor_id.strip()


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        environment=settings.environment,
    )


@router.get("/ready", response_model=ReadyResponse)
async def ready(settings: Settings = Depends(get_settings)) -> ReadyResponse:
    await check_database()
    return ReadyResponse(
        status="ok",
        service=settings.service_name,
        checks={"database": "ok"},
    )


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    content, media_type = render_prometheus_metrics()
    return Response(content=content, media_type=media_type)


@router.post(
    "/api/v1/workflows",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow(
    payload: WorkflowCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> WorkflowResponse:
    service = WorkflowService(session)
    try:
        workflow = await service.create_workflow(
            payload,
            correlation_id=request.state.correlation_id,
            actor_id=request.headers.get("X-Actor-ID", "system"),
        )
        record_workflow_creation(workflow_type=payload.workflow_type.value, status="created")
    except Exception:
        record_workflow_creation(workflow_type=payload.workflow_type.value, status="failed")
        raise

    if settings.enable_event_publishing:
        publisher = WorkflowEventPublisher(settings)
        await publisher.publish_event_by_id(session, f"{workflow.workflow_id}:workflow.created")

    if settings.enable_temporal_start:
        starter = TemporalWorkflowStarter(settings)
        temporal_workflow_id, temporal_run_id = await starter.start_mortgage_exception_review(
            workflow_id=UUID(workflow.workflow_id),
            correlation_id=request.state.correlation_id,
        )
        workflow = await service.update_temporal_metadata(
            UUID(workflow.workflow_id),
            temporal_workflow_id=temporal_workflow_id,
            temporal_run_id=temporal_run_id,
        )

    logger.info(
        "workflow created",
        extra={
            "workflow_id": workflow.workflow_id,
            "correlation_id": workflow.correlation_id,
            "operation": "workflow_create",
            "status": "created",
        },
    )
    return workflow_to_response(workflow)


@router.get("/api/v1/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> WorkflowResponse:
    service = WorkflowService(session)
    workflow = await service.get_workflow(workflow_id)
    return workflow_to_response(workflow)


@router.get("/api/v1/workflows/{workflow_id}/timeline", response_model=WorkflowTimelineResponse)
async def get_workflow_timeline(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> WorkflowTimelineResponse:
    service = WorkflowService(session)
    entries = await service.list_timeline_entries(workflow_id)
    return WorkflowTimelineResponse(
        workflow_id=workflow_id,
        entries=[timeline_entry_to_response(entry) for entry in entries],
    )


@router.get(
    "/api/v1/workflows/{workflow_id}/agent-executions",
    response_model=WorkflowAgentExecutionsResponse,
)
async def get_workflow_agent_executions(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> WorkflowAgentExecutionsResponse:
    service = WorkflowService(session)
    executions = await service.list_agent_executions(workflow_id)
    return WorkflowAgentExecutionsResponse(
        workflow_id=workflow_id,
        executions=[agent_execution_to_response(execution) for execution in executions],
    )


@router.get(
    "/api/v1/workflows/{workflow_id}/tool-invocations",
    response_model=WorkflowToolInvocationsResponse,
)
async def get_workflow_tool_invocations(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> WorkflowToolInvocationsResponse:
    service = WorkflowService(session)
    invocations = await service.list_tool_invocations(workflow_id)
    return WorkflowToolInvocationsResponse(
        workflow_id=workflow_id,
        invocations=[tool_invocation_to_response(invocation) for invocation in invocations],
    )


@router.get(
    "/api/v1/reviews/human-review-queue",
    response_model=HumanReviewQueueResponse,
)
async def get_human_review_queue(
    session: AsyncSession = Depends(get_session),
) -> HumanReviewQueueResponse:
    service = WorkflowService(session)
    workflows = await service.list_human_review_queue()
    items = [workflow_to_review_queue_item(workflow) for workflow in workflows]
    return HumanReviewQueueResponse(items=items, count=len(items))


@router.get(
    "/api/v1/workflows/{workflow_id}/review-context",
    response_model=WorkflowReviewContextResponse,
)
async def get_workflow_review_context(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> WorkflowReviewContextResponse:
    service = WorkflowService(session)
    workflow = await service.get_workflow(workflow_id)
    timeline = await service.list_timeline_entries(workflow_id)
    agent_executions = await service.list_agent_executions(workflow_id)
    tool_invocations = await service.list_tool_invocations(workflow_id)
    approvals = await service.list_approval_records(workflow_id)
    return WorkflowReviewContextResponse(
        workflow=workflow_to_response(workflow),
        timeline=[timeline_entry_to_response(entry) for entry in timeline],
        agent_executions=[agent_execution_to_response(execution) for execution in agent_executions],
        tool_invocations=[tool_invocation_to_response(invocation) for invocation in tool_invocations],
        approvals=[approval_to_response(approval) for approval in approvals],
    )


@router.get(
    "/api/v1/workflows/{workflow_id}/approvals",
    response_model=WorkflowApprovalsResponse,
)
async def get_workflow_approvals(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> WorkflowApprovalsResponse:
    service = WorkflowService(session)
    approvals = await service.list_approval_records(workflow_id)
    return WorkflowApprovalsResponse(
        workflow_id=workflow_id,
        approvals=[approval_to_response(approval) for approval in approvals],
    )


@router.get(
    "/api/v1/workflows/{workflow_id}/evaluations",
    response_model=WorkflowEvaluationsResponse,
)
async def get_workflow_evaluations(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> WorkflowEvaluationsResponse:
    service = WorkflowService(session)
    runs = await service.list_evaluation_runs(workflow_id)
    run_responses = []
    for run in runs:
        results = await service.list_evaluation_results(run.evaluation_run_id)
        run_responses.append(evaluation_run_to_response(run, results))
    return WorkflowEvaluationsResponse(workflow_id=workflow_id, runs=run_responses, count=len(run_responses))


@router.post(
    "/api/v1/workflows/{workflow_id}/replay-runs",
    response_model=ReplayRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_replay_run(
    workflow_id: UUID,
    payload: ReplayRunCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    actor_id: str | None = Header(default=None, alias="X-Actor-ID"),
    actor_roles: str | None = Header(default=None, alias="X-Actor-Roles"),
) -> ReplayRunResponse:
    actor = require_permission(
        actor_id,
        actor_roles,
        Permission.workflow_replay_create,
        action_name="Replay run creation",
    )
    service = WorkflowService(session)
    replay_run = await service.create_orchestrated_replay_run(
        workflow_id,
        replay_mode=payload.replay_mode,
        requested_by=actor.actor_id,
        correlation_id=request.state.correlation_id,
        replay_run_id=payload.replay_run_id,
        metadata=payload.metadata,
    )
    logger.info(
        "replay run created",
        extra={
            "workflow_id": str(workflow_id),
            "correlation_id": replay_run.correlation_id,
            "replay_run_id": replay_run.replay_run_id,
            "replay_mode": replay_run.replay_mode,
            "operation": "replay_run_create",
            "status": replay_run.status,
        },
    )
    return await replay_run_to_response(service, replay_run)


@router.get(
    "/api/v1/replay-runs/{replay_run_id}",
    response_model=ReplayRunResponse,
)
async def get_replay_run(
    replay_run_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ReplayRunResponse:
    service = WorkflowService(session)
    replay_run = await service.get_replay_run(replay_run_id)
    return await replay_run_to_response(service, replay_run)


@router.get(
    "/api/v1/workflows/{workflow_id}/replay-runs",
    response_model=WorkflowReplayRunsResponse,
)
async def get_workflow_replay_runs(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> WorkflowReplayRunsResponse:
    service = WorkflowService(session)
    runs = await service.list_replay_runs(workflow_id)
    run_responses = [await replay_run_to_response(service, run) for run in runs]
    return WorkflowReplayRunsResponse(workflow_id=workflow_id, runs=run_responses, count=len(run_responses))


@router.get(
    "/api/v1/workflows/{workflow_id}/replay-diagnostics",
    response_model=ReplayDiagnosticResponse,
)
async def get_workflow_replay_diagnostics(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ReplayDiagnosticResponse:
    service = WorkflowService(session)
    validation = await service.validate_deterministic_replay(workflow_id)
    return ReplayDiagnosticResponse(
        workflow_id=workflow_id,
        status=validation.status,
        summary=validation.summary,
        diagnostics=[replay_validation_step_to_response(step) for step in validation.steps],
    )


@router.get(
    "/api/v1/workflows/{workflow_id}/recovery-checks/{action_type}",
    response_model=WorkflowRecoveryCheckResponse,
)
async def get_workflow_recovery_check(
    workflow_id: UUID,
    action_type: RecoveryActionType,
    session: AsyncSession = Depends(get_session),
) -> WorkflowRecoveryCheckResponse:
    service = WorkflowService(session)
    check = await service.check_workflow_recovery(workflow_id, action_type=action_type)
    return recovery_check_to_response(check)


@router.post(
    "/api/v1/workflows/{workflow_id}/recovery-actions",
    response_model=RecoveryActionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_recovery_action(
    workflow_id: UUID,
    payload: RecoveryActionCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    actor_id: str | None = Header(default=None, alias="X-Actor-ID"),
    actor_roles: str | None = Header(default=None, alias="X-Actor-Roles"),
) -> RecoveryActionResponse:
    required_permissions = {
        RecoveryActionType.retry_outbox_event: (
            Permission.workflow_recovery_execute,
            Permission.events_outbox_retry,
        ),
        RecoveryActionType.mark_outbox_event_dead_lettered: (
            Permission.workflow_recovery_execute,
            Permission.events_outbox_dead_letter,
        ),
        RecoveryActionType.reconcile_workflow_projection: (
            Permission.workflow_recovery_execute,
            Permission.workflow_projection_reconcile,
        ),
    }.get(payload.action_type, (Permission.workflow_recovery_execute,))
    actor = require_permissions(
        actor_id,
        actor_roles,
        required_permissions,
        action_name="Recovery action creation",
    )
    service = WorkflowService(session)
    if payload.action_type == RecoveryActionType.retry_outbox_event:
        if payload.target_resource_type != "workflow_event_outbox" or not payload.target_resource_id:
            raise WorkflowReviewActionError(
                error="recovery_target_required",
                message="Outbox retry recovery requires target_resource_type workflow_event_outbox and target_resource_id",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        publisher = WorkflowEventPublisher(settings) if settings.enable_event_publishing else None
        action = await service.retry_outbox_event(
            payload.target_resource_id,
            requested_by=actor.actor_id,
            reason=payload.reason,
            publisher=publisher,
        )
    elif payload.action_type == RecoveryActionType.mark_outbox_event_dead_lettered:
        if payload.target_resource_type != "workflow_event_outbox" or not payload.target_resource_id:
            raise WorkflowReviewActionError(
                error="recovery_target_required",
                message="Outbox dead-letter recovery requires target_resource_type workflow_event_outbox and target_resource_id",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        action = await service.mark_outbox_event_dead_lettered(
            payload.target_resource_id,
            requested_by=actor.actor_id,
            reason=payload.reason,
        )
    else:
        action = await service.request_workflow_recovery(
            workflow_id,
            action_type=payload.action_type,
            requested_by=actor.actor_id,
            reason=payload.reason,
            correlation_id=request.state.correlation_id,
        )

    logger.info(
        "recovery action accepted",
        extra={
            "workflow_id": action.workflow_id,
            "correlation_id": action.correlation_id,
            "recovery_action_id": action.recovery_action_id,
            "action_type": action.action_type,
            "operation": "recovery_action_create",
            "status": action.status,
        },
    )
    return recovery_action_to_response(action)


@router.get(
    "/api/v1/recovery-actions/{recovery_action_id}",
    response_model=RecoveryActionResponse,
)
async def get_recovery_action(
    recovery_action_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> RecoveryActionResponse:
    service = WorkflowService(session)
    action = await service.get_recovery_action(recovery_action_id)
    return recovery_action_to_response(action)


@router.get(
    "/api/v1/workflows/{workflow_id}/recovery-actions",
    response_model=WorkflowRecoveryActionsResponse,
)
async def get_workflow_recovery_actions(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> WorkflowRecoveryActionsResponse:
    service = WorkflowService(session)
    actions = await service.list_recovery_actions(workflow_id)
    return WorkflowRecoveryActionsResponse(
        workflow_id=workflow_id,
        actions=[recovery_action_to_response(action) for action in actions],
        count=len(actions),
    )


@router.post(
    "/api/v1/workflows/{workflow_id}/approvals",
    response_model=ApprovalDecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_approval(
    workflow_id: UUID,
    payload: ApprovalDecisionRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    actor_id: str | None = Header(default=None, alias="X-Actor-ID"),
    actor_roles: str | None = Header(default=None, alias="X-Actor-Roles"),
) -> ApprovalDecisionResponse:
    actor = require_permission(
        actor_id,
        actor_roles,
        Permission.workflow_review_decide,
        action_name="Approval decision submission",
    )

    service = WorkflowService(session)
    workflow = await service.require_human_reviewable_workflow(workflow_id)
    approval_id = uuid4()
    reviewed_at = datetime.now(timezone.utc)
    decision_payload = {
        "approval_id": str(approval_id),
        "workflow_id": str(workflow_id),
        "correlation_id": workflow.correlation_id or request.state.correlation_id,
        "decision": payload.decision.value,
        "decision_reason": payload.decision_reason,
        "comment": payload.comment,
        "reviewed_by": actor.actor_id,
        "reviewed_at": reviewed_at.isoformat(),
        "approval_metadata": {
            **payload.metadata,
            "review_channel": payload.metadata.get("review_channel", "gateway-api"),
        },
    }

    starter = TemporalWorkflowStarter(settings)
    decision_result = await starter.apply_human_review_decision(decision_payload)

    session.expire_all()
    refreshed_workflow = await service.get_workflow(workflow_id)
    approvals = await service.list_approval_records(workflow_id)
    approval = next((record for record in approvals if record.approval_id == str(approval_id)), None)
    if approval is None:
        raise WorkflowReviewActionError(
            error="approval_record_unavailable",
            message=f"Approval decision {approval_id} was accepted but no approval record was available",
            status_code=status.HTTP_502_BAD_GATEWAY,
        )

    logger.info(
        "approval decision accepted",
        extra={
            "workflow_id": str(workflow_id),
            "correlation_id": decision_payload["correlation_id"],
            "approval_id": str(approval_id),
            "decision": payload.decision.value,
            "actor_id": actor_id,
            "operation": "approval_decision",
            "status": "accepted",
        },
    )
    return ApprovalDecisionResponse(
        workflow=workflow_to_response(refreshed_workflow),
        approval=approval_to_response(approval),
        decision_result=decision_result,
    )
