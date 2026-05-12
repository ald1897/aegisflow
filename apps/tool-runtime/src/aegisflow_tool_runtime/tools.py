from hashlib import sha256
from uuid import uuid5, NAMESPACE_URL

from pydantic import ValidationError

from aegisflow_tool_runtime.registry import TOOL_REGISTRY
from aegisflow_tool_runtime.schemas import (
    BorrowerProfileLookupInput,
    BorrowerProfileLookupOutput,
    DocumentFetchInput,
    DocumentFetchOutput,
    FraudSignalLookupInput,
    FraudSignalLookupOutput,
    PermissionStatus,
    ToolInvocationRequest,
    ToolInvocationResponse,
    ToolInvocationStatus,
    ValidationStatus,
)


class ToolNotFoundError(Exception):
    pass


class ToolPermissionDeniedError(Exception):
    pass


class ToolInputValidationError(Exception):
    pass


class ToolRuntime:
    def list_tools(self) -> list:
        return list(TOOL_REGISTRY.values())

    def invoke(self, tool_id: str, request: ToolInvocationRequest) -> ToolInvocationResponse:
        tool = TOOL_REGISTRY.get(tool_id)
        if tool is None:
            raise ToolNotFoundError(tool_id)

        if request.agent_id not in tool.allowed_agents:
            raise ToolPermissionDeniedError(f"{request.agent_id} is not allowed to invoke {tool_id}")

        input_model, output_model, handler = self._tool_definition(tool_id)
        try:
            validated_input = input_model.model_validate(request.input)
        except ValidationError as exc:
            raise ToolInputValidationError(str(exc)) from exc

        output = handler(validated_input)
        validated_output = output_model.model_validate(output.model_dump())
        invocation_id = self._invocation_id(tool_id, request)

        return ToolInvocationResponse(
            tool_invocation_id=invocation_id,
            tool_id=tool_id,
            workflow_id=request.workflow_id,
            correlation_id=request.correlation_id,
            agent_id=request.agent_id,
            agent_execution_id=request.agent_execution_id,
            status=ToolInvocationStatus.completed,
            permission_status=PermissionStatus.authorized,
            input_validation_status=ValidationStatus.validated,
            output_validation_status=ValidationStatus.validated,
            output=validated_output.model_dump(),
            telemetry={
                "tool_id": tool_id,
                "workflow_id": request.workflow_id,
                "correlation_id": request.correlation_id,
                "agent_id": request.agent_id,
                "agent_execution_id": request.agent_execution_id,
                "idempotency_key": request.idempotency_key,
                "replay_safe": tool.replay_safe,
                "data_classification": tool.data_classification,
            },
        )

    def _tool_definition(self, tool_id: str):
        if tool_id == "borrower_profile_lookup":
            return BorrowerProfileLookupInput, BorrowerProfileLookupOutput, _borrower_profile_lookup
        if tool_id == "document_fetch":
            return DocumentFetchInput, DocumentFetchOutput, _document_fetch
        if tool_id == "fraud_signal_lookup":
            return FraudSignalLookupInput, FraudSignalLookupOutput, _fraud_signal_lookup
        raise ToolNotFoundError(tool_id)

    def _invocation_id(self, tool_id: str, request: ToolInvocationRequest) -> str:
        stable_source = request.idempotency_key or (
            f"{request.workflow_id}:{request.agent_execution_id}:{request.agent_id}:{tool_id}:{request.input}"
        )
        return str(uuid5(NAMESPACE_URL, stable_source))


def _case_bucket(case_reference: str) -> int:
    return int(sha256(case_reference.encode("utf-8")).hexdigest(), 16) % 3


def _borrower_profile_lookup(payload: BorrowerProfileLookupInput) -> BorrowerProfileLookupOutput:
    bucket = _case_bucket(payload.case_reference)
    occupancy = ["PRIMARY_RESIDENCE", "SECOND_HOME", "INVESTMENT_PROPERTY"][bucket]
    channel = ["RETAIL", "BROKER", "CORRESPONDENT"][bucket]
    suffix = sha256(payload.case_reference.encode("utf-8")).hexdigest()[:6].upper()
    return BorrowerProfileLookupOutput(
        profile_status="FOUND",
        masked_borrower_reference=f"BRW-***-{suffix}",
        occupancy_type=occupancy,
        loan_channel=channel,
        profile_completeness="COMPLETE" if bucket != 2 else "PARTIAL",
    )


def _document_fetch(payload: DocumentFetchInput) -> DocumentFetchOutput:
    available_seed = {"income_verification", "exception_rationale"}
    if _case_bucket(payload.case_reference) == 1:
        available_seed.add("bank_statement")

    requested = list(dict.fromkeys(payload.requested_document_types))
    available = [document_type for document_type in requested if document_type in available_seed]
    missing = [document_type for document_type in requested if document_type not in available_seed]
    return DocumentFetchOutput(
        available_document_types=available,
        missing_document_types=missing,
        document_metadata_summary=(
            f"{len(available)} requested document types available; "
            f"{len(missing)} requested document types missing. Raw document content was not returned."
        ),
    )


def _fraud_signal_lookup(payload: FraudSignalLookupInput) -> FraudSignalLookupOutput:
    bucket = _case_bucket(payload.case_reference)
    indicators = [] if bucket == 0 else ["identity_review_signal"]
    if bucket == 2:
        indicators.append("income_consistency_review_signal")
    return FraudSignalLookupOutput(
        signal_status="CLEAR" if not indicators else "REVIEW_RECOMMENDED",
        risk_indicators=indicators,
        review_recommendation="STANDARD_REVIEW" if not indicators else "ENHANCED_HUMAN_REVIEW",
    )
