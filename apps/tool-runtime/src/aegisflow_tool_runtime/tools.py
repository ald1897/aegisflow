from hashlib import sha256
import logging
from time import perf_counter
from uuid import uuid5, NAMESPACE_URL

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from pydantic import ValidationError

from aegisflow_tool_runtime.logging import bind_log_context
from aegisflow_tool_runtime.metrics import record_tool_handler_duration, record_tool_invocation
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
from aegisflow_tool_runtime.telemetry import set_span_attributes

logger = logging.getLogger(__name__)


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
        start_time = perf_counter()
        tracer = trace.get_tracer(__name__)
        tool = TOOL_REGISTRY.get(tool_id)
        if tool is None:
            record_tool_invocation(
                tool_id=tool_id,
                status=ToolInvocationStatus.failed.value,
                permission_status="UNKNOWN",
                input_validation_status="NOT_APPLICABLE",
                output_validation_status="NOT_APPLICABLE",
                duration_seconds=perf_counter() - start_time,
            )
            raise ToolNotFoundError(tool_id)

        with bind_log_context(
            workflow_id=request.workflow_id,
            correlation_id=request.correlation_id,
            agent_id=request.agent_id,
            agent_execution_id=request.agent_execution_id,
            tool_id=tool_id,
        ):
            logger.info(
                "tool invocation started",
                extra={
                    "workflow_id": request.workflow_id,
                    "correlation_id": request.correlation_id,
                    "agent_id": request.agent_id,
                    "tool_id": tool_id,
                },
            )
        with tracer.start_as_current_span("tool_runtime.invoke_tool") as span:
            span.set_attribute("workflow_id", request.workflow_id)
            span.set_attribute("correlation_id", request.correlation_id)
            span.set_attribute("agent_id", request.agent_id)
            span.set_attribute("agent_execution_id", request.agent_execution_id or "")
            span.set_attribute("tool_id", tool_id)
            span.set_attribute("tool.data_classification", tool.data_classification)
            span.set_attribute("tool.replay_safe", tool.replay_safe)

            if request.agent_id not in tool.allowed_agents:
                span.set_attribute("tool.permission_status", PermissionStatus.denied.value)
                span.set_status(Status(StatusCode.ERROR))
                record_tool_invocation(
                    tool_id=tool_id,
                    status=ToolInvocationStatus.failed.value,
                    permission_status=PermissionStatus.denied.value,
                    input_validation_status="NOT_APPLICABLE",
                    output_validation_status="NOT_APPLICABLE",
                    duration_seconds=perf_counter() - start_time,
                )
                logger.warning(
                    "tool invocation denied",
                    extra={
                        "workflow_id": request.workflow_id,
                        "correlation_id": request.correlation_id,
                        "agent_id": request.agent_id,
                        "tool_id": tool_id,
                        "permission_status": PermissionStatus.denied.value,
                        "status": ToolInvocationStatus.failed.value,
                    },
                )
                raise ToolPermissionDeniedError(f"{request.agent_id} is not allowed to invoke {tool_id}")

            input_model, output_model, handler = self._tool_definition(tool_id)
            try:
                validated_input = input_model.model_validate(request.input)
            except ValidationError as exc:
                span.set_attribute("tool.permission_status", PermissionStatus.authorized.value)
                span.set_attribute("tool.input_validation_status", ValidationStatus.rejected.value)
                span.set_status(Status(StatusCode.ERROR))
                record_tool_invocation(
                    tool_id=tool_id,
                    status=ToolInvocationStatus.failed.value,
                    permission_status=PermissionStatus.authorized.value,
                    input_validation_status=ValidationStatus.rejected.value,
                    output_validation_status="NOT_APPLICABLE",
                    duration_seconds=perf_counter() - start_time,
                )
                logger.warning(
                    "tool input validation rejected",
                    extra={
                        "workflow_id": request.workflow_id,
                        "correlation_id": request.correlation_id,
                        "agent_id": request.agent_id,
                        "tool_id": tool_id,
                        "validation_status": ValidationStatus.rejected.value,
                        "status": ToolInvocationStatus.failed.value,
                    },
                )
                raise ToolInputValidationError(str(exc)) from exc

            handler_start_time = perf_counter()
            try:
                output = handler(validated_input)
                record_tool_handler_duration(
                    tool_id=tool_id,
                    status="completed",
                    duration_seconds=perf_counter() - handler_start_time,
                )
                validated_output = output_model.model_validate(output.model_dump())
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                record_tool_handler_duration(
                    tool_id=tool_id,
                    status="failed",
                    duration_seconds=perf_counter() - handler_start_time,
                )
                record_tool_invocation(
                    tool_id=tool_id,
                    status=ToolInvocationStatus.failed.value,
                    permission_status=PermissionStatus.authorized.value,
                    input_validation_status=ValidationStatus.validated.value,
                    output_validation_status=ValidationStatus.rejected.value,
                    duration_seconds=perf_counter() - start_time,
                )
                logger.exception(
                    "tool output validation failed",
                    extra={
                        "workflow_id": request.workflow_id,
                        "correlation_id": request.correlation_id,
                        "agent_id": request.agent_id,
                        "tool_id": tool_id,
                        "status": ToolInvocationStatus.failed.value,
                    },
                )
                raise

            invocation_id = self._invocation_id(tool_id, request)
            response = ToolInvocationResponse(
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
            record_tool_invocation(
                tool_id=tool_id,
                status=response.status.value,
                permission_status=response.permission_status.value,
                input_validation_status=response.input_validation_status.value,
                output_validation_status=response.output_validation_status.value,
                duration_seconds=perf_counter() - start_time,
            )
            set_span_attributes(
                {
                    "tool_invocation_id": invocation_id,
                    "tool.status": response.status.value,
                    "tool.permission_status": response.permission_status.value,
                    "tool.input_validation_status": response.input_validation_status.value,
                    "tool.output_validation_status": response.output_validation_status.value,
                }
            )
            logger.info(
                "tool invocation completed",
                extra={
                    "workflow_id": request.workflow_id,
                    "correlation_id": request.correlation_id,
                    "agent_id": request.agent_id,
                    "agent_execution_id": request.agent_execution_id,
                    "tool_id": tool_id,
                    "status": response.status.value,
                    "permission_status": response.permission_status.value,
                },
            )
            return response

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
