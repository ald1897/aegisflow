from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from aegisflow_gateway.domain.workflows import WorkflowPriority, WorkflowState, WorkflowType


class WorkflowCreateRequest(BaseModel):
    workflow_type: WorkflowType = WorkflowType.mortgage_exception_review
    priority: WorkflowPriority = WorkflowPriority.normal
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowResponse(BaseModel):
    workflow_id: UUID
    workflow_type: WorkflowType
    state: WorkflowState
    priority: WorkflowPriority
    correlation_id: str
    created_at: datetime
    updated_at: datetime
    temporal_workflow_id: str | None = None
    temporal_run_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    metadata: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


class ReadyResponse(BaseModel):
    status: str
    service: str
    checks: dict[str, str]


class ErrorResponse(BaseModel):
    error: str
    message: str
    correlation_id: str | None = None


class WorkflowTimelineEntryResponse(BaseModel):
    timeline_entry_id: UUID
    workflow_id: UUID
    entry_type: str
    message: str
    state: WorkflowState | None
    correlation_id: str
    created_by: str
    created_at: datetime
    metadata: dict[str, Any]


class WorkflowTimelineResponse(BaseModel):
    workflow_id: UUID
    entries: list[WorkflowTimelineEntryResponse]


class AgentExecutionRecordResponse(BaseModel):
    agent_execution_id: UUID
    workflow_id: UUID
    agent_id: str
    prompt_id: str
    prompt_version: str
    model_name: str
    status: str
    validation_status: str
    confidence_score: float
    requires_human_review: bool
    output: dict[str, Any]
    metadata: dict[str, Any]
    correlation_id: str
    created_by: str
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime


class WorkflowAgentExecutionsResponse(BaseModel):
    workflow_id: UUID
    executions: list[AgentExecutionRecordResponse]


class ToolInvocationRecordResponse(BaseModel):
    tool_invocation_id: UUID
    workflow_id: UUID
    agent_execution_id: UUID | None
    agent_id: str
    tool_id: str
    status: str
    permission_status: str
    input_validation_status: str
    output_validation_status: str
    input_metadata: dict[str, Any]
    output: dict[str, Any]
    metadata: dict[str, Any]
    error_message: str | None
    correlation_id: str
    created_by: str
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime


class WorkflowToolInvocationsResponse(BaseModel):
    workflow_id: UUID
    invocations: list[ToolInvocationRecordResponse]
