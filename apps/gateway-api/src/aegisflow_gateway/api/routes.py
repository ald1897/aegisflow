import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from aegisflow_gateway.api.schemas import (
    AgentExecutionRecordResponse,
    HealthResponse,
    ReadyResponse,
    ToolInvocationRecordResponse,
    WorkflowAgentExecutionsResponse,
    WorkflowCreateRequest,
    WorkflowResponse,
    WorkflowToolInvocationsResponse,
    WorkflowTimelineEntryResponse,
    WorkflowTimelineResponse,
)
from aegisflow_gateway.config import Settings, get_settings
from aegisflow_gateway.persistence.database import check_database, get_session
from aegisflow_gateway.persistence.models import (
    AgentExecutionRecord,
    ToolInvocationRecord,
    WorkflowRecord,
    WorkflowTimelineEntry,
)
from aegisflow_gateway.services.events import WorkflowEventPublisher
from aegisflow_gateway.services.temporal import TemporalWorkflowStarter
from aegisflow_gateway.services.workflows import WorkflowNotFoundError, WorkflowService

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
