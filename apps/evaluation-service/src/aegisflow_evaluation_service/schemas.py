from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class EvaluationRunCreate(BaseModel):
    evaluation_run_id: UUID = Field(default_factory=uuid4)
    workflow_id: UUID
    correlation_id: str = Field(min_length=1, max_length=128)
    evaluation_scope: str = Field(min_length=1, max_length=80)
    evaluation_mode: str = Field(min_length=1, max_length=80)
    dataset_id: str | None = Field(default=None, max_length=120)
    status: str = Field(min_length=1, max_length=40)
    started_at: datetime
    completed_at: datetime | None = None
    created_by: str = Field(min_length=1, max_length=128)
    run_metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationRunRead(BaseModel):
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
    run_metadata: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationResultCreate(BaseModel):
    evaluation_result_id: UUID = Field(default_factory=uuid4)
    evaluation_run_id: UUID
    workflow_id: UUID
    agent_execution_id: UUID | None = None
    prompt_id: str | None = Field(default=None, max_length=120)
    prompt_version: str | None = Field(default=None, max_length=40)
    model_name: str | None = Field(default=None, max_length=120)
    evaluator_id: str = Field(min_length=1, max_length=120)
    evaluator_version: str = Field(min_length=1, max_length=40)
    score_name: str = Field(min_length=1, max_length=120)
    score_value: float
    score_status: str = Field(min_length=1, max_length=40)
    severity: str = Field(min_length=1, max_length=40)
    rationale: str = Field(min_length=1, max_length=1000)
    result_metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationResultRead(BaseModel):
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
    result_metadata: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationDatasetCaseCreate(BaseModel):
    dataset_case_id: str = Field(min_length=1, max_length=128)
    dataset_id: str = Field(min_length=1, max_length=120)
    case_name: str = Field(min_length=1, max_length=255)
    workflow_type: str = Field(min_length=1, max_length=80)
    expected_agents: dict[str, Any] = Field(default_factory=dict)
    expected_tools: dict[str, Any] = Field(default_factory=dict)
    expected_human_review: bool
    expected_decision: str | None = Field(default=None, max_length=40)
    expected_signals: dict[str, Any] = Field(default_factory=dict)
    case_metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationDatasetCaseRead(BaseModel):
    dataset_case_id: str
    dataset_id: str
    case_name: str
    workflow_type: str
    expected_agents: dict[str, Any]
    expected_tools: dict[str, Any]
    expected_human_review: bool
    expected_decision: str | None
    expected_signals: dict[str, Any]
    case_metadata: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
