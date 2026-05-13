from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from aegisflow_gateway.domain.workflows import (
    ApprovalDecision,
    RecoveryActionStatus,
    RecoveryActionType,
    ReplayMode,
    ReplayRunStatus,
    ReplayStepStatus,
    WorkflowPriority,
    WorkflowState,
    WorkflowType,
)


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


class ApprovalRecordResponse(BaseModel):
    approval_id: UUID
    workflow_id: UUID
    decision: ApprovalDecision
    decision_reason: str
    comment: str
    reviewed_by: str
    reviewed_at: datetime
    metadata: dict[str, Any]
    correlation_id: str
    created_at: datetime


class WorkflowApprovalsResponse(BaseModel):
    workflow_id: UUID
    approvals: list[ApprovalRecordResponse]


class HumanReviewQueueItemResponse(BaseModel):
    workflow_id: UUID
    workflow_type: WorkflowType
    state: WorkflowState
    priority: WorkflowPriority
    correlation_id: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]


class HumanReviewQueueResponse(BaseModel):
    items: list[HumanReviewQueueItemResponse]
    count: int


class WorkflowReviewContextResponse(BaseModel):
    workflow: WorkflowResponse
    timeline: list[WorkflowTimelineEntryResponse]
    agent_executions: list[AgentExecutionRecordResponse]
    tool_invocations: list[ToolInvocationRecordResponse]
    approvals: list[ApprovalRecordResponse]


class ApprovalDecisionRequest(BaseModel):
    decision: ApprovalDecision
    decision_reason: str = Field(min_length=1, max_length=255)
    comment: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalDecisionResponse(BaseModel):
    workflow: WorkflowResponse
    approval: ApprovalRecordResponse
    decision_result: dict[str, Any]


class EvaluationResultResponse(BaseModel):
    evaluation_result_id: UUID
    evaluation_run_id: UUID
    workflow_id: UUID
    agent_execution_id: UUID | None
    prompt_id: str | None
    prompt_version: str | None
    model_name: str | None
    evaluator_id: str
    evaluator_version: str
    score_name: str
    score_value: float
    score_status: str
    severity: str
    rationale: str
    metadata: dict[str, Any]
    created_at: datetime


class EvaluationRunSummaryResponse(BaseModel):
    evaluation_run_id: UUID
    workflow_id: UUID
    correlation_id: str
    evaluation_scope: str
    evaluation_mode: str
    dataset_id: str | None
    status: str
    started_at: datetime
    completed_at: datetime | None
    created_by: str
    metadata: dict[str, Any]
    created_at: datetime
    results: list[EvaluationResultResponse]


class WorkflowEvaluationsResponse(BaseModel):
    workflow_id: UUID
    runs: list[EvaluationRunSummaryResponse]
    count: int


class ReplayRunCreateRequest(BaseModel):
    replay_mode: ReplayMode = ReplayMode.deterministic_validation
    replay_run_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReplayStepResponse(BaseModel):
    replay_step_id: UUID
    replay_run_id: UUID
    workflow_id: UUID
    sequence_number: int
    artifact_type: str
    artifact_id: str | None
    expected_state: str | None
    observed_state: str | None
    status: ReplayStepStatus
    message: str
    metadata: dict[str, Any]
    created_at: datetime


class ReplayRunResponse(BaseModel):
    replay_run_id: UUID
    workflow_id: UUID
    correlation_id: str
    replay_mode: ReplayMode
    status: ReplayRunStatus
    source_temporal_workflow_id: str | None
    source_temporal_run_id: str | None
    started_at: datetime
    completed_at: datetime | None
    requested_by: str
    metadata: dict[str, Any]
    created_at: datetime
    steps: list[ReplayStepResponse] = Field(default_factory=list)


class WorkflowReplayRunsResponse(BaseModel):
    workflow_id: UUID
    runs: list[ReplayRunResponse]
    count: int


class ReplayDiagnosticStepResponse(BaseModel):
    sequence_number: int
    artifact_type: str
    artifact_id: str | None
    expected_state: str | None
    observed_state: str | None
    status: ReplayStepStatus
    message: str
    metadata: dict[str, Any]


class ReplayDiagnosticResponse(BaseModel):
    workflow_id: UUID
    status: ReplayStepStatus
    summary: str
    diagnostics: list[ReplayDiagnosticStepResponse]


class RecoveryActionCreateRequest(BaseModel):
    action_type: RecoveryActionType
    target_resource_type: str | None = Field(default=None, max_length=80)
    target_resource_id: str | None = Field(default=None, max_length=128)
    reason: str = Field(min_length=1, max_length=1000)


class RecoveryActionResponse(BaseModel):
    recovery_action_id: UUID
    workflow_id: UUID
    correlation_id: str
    action_type: RecoveryActionType
    target_resource_type: str
    target_resource_id: str
    status: RecoveryActionStatus
    requested_by: str
    reason: str
    started_at: datetime
    completed_at: datetime | None
    metadata: dict[str, Any]
    created_at: datetime


class WorkflowRecoveryActionsResponse(BaseModel):
    workflow_id: UUID
    actions: list[RecoveryActionResponse]
    count: int


class WorkflowRecoveryCheckResponse(BaseModel):
    workflow_id: UUID
    action_type: RecoveryActionType
    target_resource_type: str
    target_resource_id: str
    allowed: bool
    current_state: str
    proposed_state: str | None
    reason: str
    requires_engine_execution: bool
    metadata: dict[str, Any]
