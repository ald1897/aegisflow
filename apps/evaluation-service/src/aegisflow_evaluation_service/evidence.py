from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentExecutionEvidence:
    agent_execution_id: str
    agent_id: str
    prompt_id: str
    prompt_version: str
    model_name: str
    status: str
    validation_status: str
    confidence_score: float
    requires_human_review: bool
    output_payload: dict[str, Any] = field(default_factory=dict)
    execution_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolInvocationEvidence:
    tool_invocation_id: str
    agent_execution_id: str | None
    agent_id: str
    tool_id: str
    status: str
    permission_status: str
    input_validation_status: str
    output_validation_status: str
    output_payload: dict[str, Any] = field(default_factory=dict)
    execution_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowEvaluationEvidence:
    workflow_id: str
    workflow_type: str
    workflow_state: str
    correlation_id: str
    agent_executions: tuple[AgentExecutionEvidence, ...] = ()
    tool_invocations: tuple[ToolInvocationEvidence, ...] = ()
    approval_decision: str | None = None


@dataclass(frozen=True)
class EvaluationExpectations:
    expected_agents: tuple[str, ...] = ()
    expected_tools: tuple[str, ...] = ()
    expected_human_review: bool | None = None
    expected_terminal_decision: str | None = None
