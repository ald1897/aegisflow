from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolInvocationStatus(StrEnum):
    completed = "COMPLETED"
    failed = "FAILED"


class PermissionStatus(StrEnum):
    authorized = "AUTHORIZED"
    denied = "DENIED"


class ValidationStatus(StrEnum):
    validated = "VALIDATED"
    rejected = "REJECTED"


class ToolDefinition(BaseModel):
    tool_id: str
    display_name: str
    description: str
    allowed_agents: list[str]
    input_schema: str
    output_schema: str
    data_classification: str
    replay_safe: bool


class ToolRegistryResponse(BaseModel):
    tools: list[ToolDefinition]


class ToolInvocationRequest(BaseModel):
    workflow_id: str
    correlation_id: str
    agent_id: str
    agent_execution_id: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


class ToolInvocationResponse(BaseModel):
    tool_invocation_id: str
    tool_id: str
    workflow_id: str
    correlation_id: str
    agent_id: str
    agent_execution_id: str | None
    status: ToolInvocationStatus
    permission_status: PermissionStatus
    input_validation_status: ValidationStatus
    output_validation_status: ValidationStatus
    output: dict[str, Any]
    telemetry: dict[str, Any]


class BorrowerProfileLookupInput(BaseModel):
    workflow_id: str
    correlation_id: str
    case_reference: str = Field(min_length=1, max_length=80)


class BorrowerProfileLookupOutput(BaseModel):
    output_type: Literal["borrower_profile_lookup_output"] = "borrower_profile_lookup_output"
    profile_status: Literal["FOUND", "NOT_FOUND"]
    masked_borrower_reference: str
    occupancy_type: Literal["PRIMARY_RESIDENCE", "SECOND_HOME", "INVESTMENT_PROPERTY"]
    loan_channel: Literal["RETAIL", "BROKER", "CORRESPONDENT"]
    profile_completeness: Literal["COMPLETE", "PARTIAL"]
    validation_status: Literal["VALIDATED"] = "VALIDATED"


class DocumentFetchInput(BaseModel):
    workflow_id: str
    correlation_id: str
    case_reference: str = Field(min_length=1, max_length=80)
    requested_document_types: list[str] = Field(min_length=1, max_length=10)


class DocumentFetchOutput(BaseModel):
    output_type: Literal["document_fetch_output"] = "document_fetch_output"
    available_document_types: list[str]
    missing_document_types: list[str]
    document_metadata_summary: str
    validation_status: Literal["VALIDATED"] = "VALIDATED"


class FraudSignalLookupInput(BaseModel):
    workflow_id: str
    correlation_id: str
    case_reference: str = Field(min_length=1, max_length=80)


class FraudSignalLookupOutput(BaseModel):
    output_type: Literal["fraud_signal_lookup_output"] = "fraud_signal_lookup_output"
    signal_status: Literal["CLEAR", "REVIEW_RECOMMENDED"]
    risk_indicators: list[str]
    review_recommendation: Literal["STANDARD_REVIEW", "ENHANCED_HUMAN_REVIEW"]
    validation_status: Literal["VALIDATED"] = "VALIDATED"
