from collections.abc import Callable
from typing import Any, Protocol, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from aegisflow_agent_runtime.prompts import PromptAsset, PromptRegistry
from aegisflow_agent_runtime.registry import AGENT_REGISTRY
from aegisflow_agent_runtime.schemas import (
    AgentExecutionRequest,
    AgentExecutionResponse,
    AgentExecutionStatus,
    AgentValidationStatus,
    DocumentAnalysisAgentOutput,
    IntakeAgentOutput,
)
from aegisflow_agent_runtime.tools import ToolInvocationContext, ToolRuntimeClient, ToolRuntimeError


class AgentGraphState(TypedDict, total=False):
    request: AgentExecutionRequest
    prompt: PromptAsset
    tool_context: dict[str, ToolInvocationContext]
    output: dict[str, Any]
    validation_status: str


class ToolClient(Protocol):
    def invoke(
        self,
        *,
        tool_id: str,
        agent_id: str,
        agent_execution_id: str,
        request: AgentExecutionRequest,
        input_payload: dict[str, Any],
    ) -> ToolInvocationContext | None:
        pass


class AgentNotFoundError(Exception):
    pass


class UnsupportedWorkflowStateError(Exception):
    pass


class UnauthorizedToolRequestError(Exception):
    pass


class AgentRuntime:
    def __init__(self, prompt_registry: PromptRegistry, tool_client: ToolClient | None = None) -> None:
        self.prompt_registry = prompt_registry
        self.tool_client = tool_client or ToolRuntimeClient("http://localhost:8020", enabled=False)

    def list_agents(self) -> list:
        return list(AGENT_REGISTRY.values())

    def execute(self, agent_id: str, request: AgentExecutionRequest) -> AgentExecutionResponse:
        registry_entry = AGENT_REGISTRY.get(agent_id)
        if registry_entry is None:
            raise AgentNotFoundError(agent_id)

        if request.workflow_state not in registry_entry.supported_workflow_states:
            raise UnsupportedWorkflowStateError(
                f"{agent_id} does not support workflow state {request.workflow_state}"
            )

        prompt = self.prompt_registry.load(registry_entry.prompt_id, registry_entry.prompt_version)
        execution_id = str(uuid4())
        tool_context = self._collect_tool_context(
            agent_id=agent_id,
            allowed_tools=registry_entry.allowed_tools,
            agent_execution_id=execution_id,
            request=request,
        )
        output_model, generator = self._agent_definition(agent_id)
        graph = self._build_graph(generator=generator, output_model=output_model)
        result = graph.invoke({"request": request, "prompt": prompt, "tool_context": tool_context})
        output = result["output"]

        return AgentExecutionResponse(
            execution_id=execution_id,
            agent_id=agent_id,
            status=AgentExecutionStatus.completed,
            validation_status=AgentValidationStatus.validated,
            prompt_id=prompt.prompt_id,
            prompt_version=prompt.version,
            model_name="deterministic-langgraph-local-v1",
            confidence_score=float(output["confidence_score"]),
            requires_human_review=bool(output["requires_human_review"]),
            output=output,
            telemetry={
                "workflow_id": request.workflow_id,
                "correlation_id": request.correlation_id,
                "workflow_state": request.workflow_state,
                "prompt_path": str(prompt.path),
                "allowed_tools": registry_entry.allowed_tools,
                "tool_invocations": [
                    {
                        "tool_invocation_id": invocation.tool_invocation_id,
                        "tool_id": invocation.tool_id,
                        "status": invocation.status,
                        "permission_status": invocation.permission_status,
                        "input_validation_status": invocation.input_validation_status,
                        "output_validation_status": invocation.output_validation_status,
                        "telemetry": invocation.telemetry,
                    }
                    for invocation in tool_context.values()
                ],
            },
        )

    def _build_graph(
        self,
        *,
        generator: Callable[[AgentExecutionRequest, PromptAsset, dict[str, ToolInvocationContext]], BaseModel],
        output_model: type[BaseModel],
    ):
        graph = StateGraph(AgentGraphState)

        def assemble_context(state: AgentGraphState) -> AgentGraphState:
            return state

        def execute_agent(state: AgentGraphState) -> AgentGraphState:
            request = state["request"]
            prompt = state["prompt"]
            state["output"] = generator(request, prompt, state.get("tool_context", {})).model_dump()
            return state

        def validate_output(state: AgentGraphState) -> AgentGraphState:
            validated = output_model.model_validate(state["output"])
            state["output"] = validated.model_dump()
            state["validation_status"] = AgentValidationStatus.validated.value
            return state

        graph.add_node("assemble_context", assemble_context)
        graph.add_node("execute_agent", execute_agent)
        graph.add_node("validate_output", validate_output)
        graph.add_edge(START, "assemble_context")
        graph.add_edge("assemble_context", "execute_agent")
        graph.add_edge("execute_agent", "validate_output")
        graph.add_edge("validate_output", END)
        return graph.compile()

    def _collect_tool_context(
        self,
        *,
        agent_id: str,
        allowed_tools: list[str],
        agent_execution_id: str,
        request: AgentExecutionRequest,
    ) -> dict[str, ToolInvocationContext]:
        tool_requests = _tool_requests_for_agent(agent_id, request)
        context: dict[str, ToolInvocationContext] = {}
        for tool_id, input_payload in tool_requests.items():
            if tool_id not in allowed_tools:
                raise UnauthorizedToolRequestError(f"{agent_id} is not allowed to invoke {tool_id}")
            try:
                invocation = self.tool_client.invoke(
                    tool_id=tool_id,
                    agent_id=agent_id,
                    agent_execution_id=agent_execution_id,
                    request=request,
                    input_payload=input_payload,
                )
            except ToolRuntimeError:
                continue
            if invocation is not None:
                context[tool_id] = invocation
        return context

    def _agent_definition(self, agent_id: str):
        if agent_id == "intake_agent":
            return IntakeAgentOutput, _execute_intake_agent
        if agent_id == "document_analysis_agent":
            return DocumentAnalysisAgentOutput, _execute_document_analysis_agent
        raise AgentNotFoundError(agent_id)


def _tool_requests_for_agent(
    agent_id: str,
    request: AgentExecutionRequest,
) -> dict[str, dict[str, Any]]:
    case_reference = request.metadata.get("case_reference")
    if not case_reference:
        return {}
    if agent_id == "intake_agent":
        return {
            "borrower_profile_lookup": {
                "workflow_id": request.workflow_id,
                "correlation_id": request.correlation_id,
                "case_reference": case_reference,
            }
        }
    if agent_id == "document_analysis_agent":
        return {
            "document_fetch": {
                "workflow_id": request.workflow_id,
                "correlation_id": request.correlation_id,
                "case_reference": case_reference,
                "requested_document_types": ["income_verification", "exception_rationale"],
            }
        }
    return {}


def _execute_intake_agent(
    request: AgentExecutionRequest,
    prompt: PromptAsset,
    tool_context: dict[str, ToolInvocationContext],
) -> IntakeAgentOutput:
    del prompt
    case_reference = request.metadata.get("case_reference")
    borrower_profile = tool_context.get("borrower_profile_lookup")
    missing_fields = [
        field_name
        for field_name in ("case_reference", "channel")
        if not request.metadata.get(field_name)
    ]
    ready = not missing_fields
    return IntakeAgentOutput(
        case_reference=case_reference,
        intake_classification="MORTGAGE_EXCEPTION_REVIEW",
        readiness="READY_FOR_DOCUMENT_ANALYSIS" if ready else "REQUIRES_OPERATOR_REVIEW",
        missing_fields=missing_fields,
        recommended_next_state="DOCUMENT_ANALYSIS_PENDING",
        summary=(
            _intake_summary(borrower_profile)
            if ready
            else "Mortgage exception intake is missing required routing context; downstream review must preserve human oversight."
        ),
        confidence_score=0.91 if ready else 0.72,
        requires_human_review=not ready,
    )


def _execute_document_analysis_agent(
    request: AgentExecutionRequest,
    prompt: PromptAsset,
    tool_context: dict[str, ToolInvocationContext],
) -> DocumentAnalysisAgentOutput:
    del prompt
    document_fetch = tool_context.get("document_fetch")
    provided_documents = set(request.metadata.get("documents", []))
    required_documents = {"income_verification", "exception_rationale"}
    available_documents = set(provided_documents)
    if document_fetch is not None:
        available_documents.update(document_fetch.output.get("available_document_types", []))
    missing_documents = sorted(required_documents - available_documents)
    complete = not missing_documents
    risk_flags = [] if complete else ["missing_supporting_documentation"]
    return DocumentAnalysisAgentOutput(
        document_status="COMPLETE" if complete else "INCOMPLETE",
        extracted_signals=[
            "mortgage_exception_review_case",
            "operator_decision_required",
        ],
        missing_documents=missing_documents,
        risk_flags=risk_flags,
        risk_level="LOW" if complete else "MEDIUM",
        recommended_next_state="RISK_REVIEW_PENDING",
        summary=(
            _document_summary(document_fetch)
            if complete
            else "Document metadata indicates missing support; risk review should preserve human oversight."
        ),
        confidence_score=0.88 if complete else 0.83,
        requires_human_review=True,
    )


def _intake_summary(invocation: ToolInvocationContext | None) -> str:
    if invocation is None:
        return "Mortgage exception intake contains enough routing context for document analysis."
    profile_status = invocation.output.get("profile_status", "UNKNOWN")
    profile_completeness = invocation.output.get("profile_completeness", "UNKNOWN")
    return (
        "Mortgage exception intake contains enough routing context for document analysis. "
        f"Governed borrower profile context returned {profile_status} with {profile_completeness} completeness."
    )


def _document_summary(invocation: ToolInvocationContext | None) -> str:
    if invocation is None:
        return "Document metadata appears sufficient for risk review preparation."
    available = invocation.output.get("available_document_types", [])
    return (
        "Document metadata appears sufficient for risk review preparation. "
        f"Governed document metadata lookup returned {len(available)} available required document types."
    )
