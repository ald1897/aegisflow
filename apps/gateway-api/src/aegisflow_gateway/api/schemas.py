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
