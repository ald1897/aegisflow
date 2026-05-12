import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from aegisflow_gateway.api.schemas import (
    AgentExecutionRecordResponse,
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    ApprovalRecordResponse,
    HealthResponse,
    HumanReviewQueueItemResponse,
    HumanReviewQueueResponse,
    ReadyResponse,
    ToolInvocationRecordResponse,
    WorkflowApprovalsResponse,
    WorkflowAgentExecutionsResponse,
    WorkflowCreateRequest,
    WorkflowReviewContextResponse,
    WorkflowResponse,
    WorkflowToolInvocationsResponse,
    WorkflowTimelineEntryResponse,
    WorkflowTimelineResponse,
)
from aegisflow_gateway.config import Settings, get_settings
from aegisflow_gateway.persistence.database import check_database, get_session
from aegisflow_gateway.persistence.models import (
    AgentExecutionRecord,
    ApprovalRecord,
    ToolInvocationRecord,
    WorkflowRecord,
    WorkflowTimelineEntry,
)
from aegisflow_gateway.services.events import WorkflowEventPublisher
from aegisflow_gateway.services.temporal import TemporalWorkflowStarter
from aegisflow_gateway.services.workflows import WorkflowReviewActionError, WorkflowService

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
    workflow = await service.create_workflow(
        payload,
        correlation_id=request.state.correlation_id,
        actor_id=request.headers.get("X-Actor-ID", "system"),
    )

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

    logger.info("workflow created", extra={"workflow_id": workflow.workflow_id})
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
) -> ApprovalDecisionResponse:
    if actor_id is None or not actor_id.strip():
        raise WorkflowReviewActionError(
            error="actor_required",
            message="Approval decisions require X-Actor-ID",
            status_code=status.HTTP_400_BAD_REQUEST,
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
        "reviewed_by": actor_id.strip(),
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

    return ApprovalDecisionResponse(
        workflow=workflow_to_response(refreshed_workflow),
        approval=approval_to_response(approval),
        decision_result=decision_result,
    )
