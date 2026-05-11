from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentExecutionStatus(StrEnum):
    completed = "COMPLETED"
    failed = "FAILED"


class AgentValidationStatus(StrEnum):
    validated = "VALIDATED"
    rejected = "REJECTED"


class AgentExecutionRequest(BaseModel):
    workflow_id: str
    correlation_id: str
    workflow_type: str
    workflow_state: str
    priority: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentRegistryEntry(BaseModel):
    agent_id: str
    display_name: str
    description: str
    prompt_id: str
    prompt_version: str
    supported_workflow_states: list[str]
    allowed_tools: list[str]
    confidence_threshold: float


class AgentRegistryResponse(BaseModel):
    agents: list[AgentRegistryEntry]


class IntakeAgentOutput(BaseModel):
    output_type: Literal["intake_agent_output"] = "intake_agent_output"
    case_reference: str | None
    intake_classification: Literal["MORTGAGE_EXCEPTION_REVIEW"]
    readiness: Literal["READY_FOR_DOCUMENT_ANALYSIS", "REQUIRES_OPERATOR_REVIEW"]
    missing_fields: list[str]
    recommended_next_state: Literal["DOCUMENT_ANALYSIS_PENDING"]
    summary: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    requires_human_review: bool


class DocumentAnalysisAgentOutput(BaseModel):
    output_type: Literal["document_analysis_agent_output"] = "document_analysis_agent_output"
    document_status: Literal["COMPLETE", "INCOMPLETE", "NEEDS_REVIEW"]
    extracted_signals: list[str]
    missing_documents: list[str]
    risk_flags: list[str]
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    recommended_next_state: Literal["RISK_REVIEW_PENDING", "HUMAN_REVIEW_REQUIRED"]
    summary: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    requires_human_review: bool


class AgentExecutionResponse(BaseModel):
    execution_id: str
    agent_id: str
    status: AgentExecutionStatus
    validation_status: AgentValidationStatus
    prompt_id: str
    prompt_version: str
    model_name: str
    confidence_score: float
    requires_human_review: bool
    output: dict[str, Any]
    telemetry: dict[str, Any]
