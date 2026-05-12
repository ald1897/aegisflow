from dataclasses import dataclass, field
from typing import Any, Protocol

from aegisflow_evaluation_service.evidence import (
    AgentExecutionEvidence,
    EvaluationExpectations,
    ToolInvocationEvidence,
    WorkflowEvaluationEvidence,
)

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

SEVERITY_INFORMATIONAL = "informational"
SEVERITY_MODERATE = "moderate"
SEVERITY_CRITICAL = "critical"

EVALUATOR_VERSION = "v1"


@dataclass(frozen=True)
class EvaluationScore:
    evaluator_id: str
    evaluator_version: str
    score_name: str
    score_value: float
    score_status: str
    severity: str
    rationale: str
    agent_execution_id: str | None = None
    prompt_id: str | None = None
    prompt_version: str | None = None
    model_name: str | None = None
    result_metadata: dict[str, Any] = field(default_factory=dict)


class DeterministicEvaluator(Protocol):
    evaluator_id: str
    evaluator_version: str

    def evaluate(
        self,
        evidence: WorkflowEvaluationEvidence,
        expectations: EvaluationExpectations | None = None,
    ) -> list[EvaluationScore]:
        ...


class AgentOutputEvaluator:
    evaluator_id = "agent-output-contract"
    evaluator_version = EVALUATOR_VERSION

    def evaluate(
        self,
        evidence: WorkflowEvaluationEvidence,
        expectations: EvaluationExpectations | None = None,
    ) -> list[EvaluationScore]:
        del expectations
        if not evidence.agent_executions:
            return [
                self._score(
                    score_name="agent_output_contract",
                    score_value=0.0,
                    score_status=FAIL,
                    severity=SEVERITY_CRITICAL,
                    rationale="No agent executions were available for evaluation.",
                    metadata={"agent_execution_count": 0},
                )
            ]

        return [self._score_agent(agent) for agent in evidence.agent_executions]

    def _score_agent(self, agent: AgentExecutionEvidence) -> EvaluationScore:
        failures: list[str] = []
        warnings: list[str] = []

        if agent.status != "COMPLETED":
            failures.append("agent status was not COMPLETED")
        if agent.validation_status != "VALIDATED":
            failures.append("agent validation status was not VALIDATED")
        if not 0.0 <= agent.confidence_score <= 1.0:
            failures.append("agent confidence score was outside the 0..1 range")
        if not isinstance(agent.requires_human_review, bool):
            failures.append("requires_human_review was not boolean")
        if not agent.prompt_id or not agent.prompt_version or not agent.model_name:
            failures.append("prompt or model metadata was missing")

        required_output_fields = {"recommended_next_state", "summary", "requires_human_review", "confidence_score"}
        missing_fields = sorted(field for field in required_output_fields if field not in agent.output_payload)
        if missing_fields:
            failures.append("agent output was missing required fields")
        if agent.output_payload.get("requires_human_review") is not None:
            output_human_review = agent.output_payload.get("requires_human_review")
            if output_human_review != agent.requires_human_review:
                warnings.append("agent output human review flag did not match persisted execution metadata")
        if agent.output_payload.get("confidence_score") is not None:
            output_confidence = agent.output_payload.get("confidence_score")
            if isinstance(output_confidence, int | float) and abs(float(output_confidence) - agent.confidence_score) > 0.001:
                warnings.append("agent output confidence did not match persisted execution metadata")

        if failures:
            return self._score(
                score_name="agent_output_contract",
                score_value=0.0,
                score_status=FAIL,
                severity=SEVERITY_CRITICAL,
                rationale=f"Agent {agent.agent_id} failed deterministic output contract checks.",
                agent=agent,
                metadata={"failures": failures, "warnings": warnings, "missing_fields": missing_fields},
            )
        if warnings:
            return self._score(
                score_name="agent_output_contract",
                score_value=0.75,
                score_status=WARN,
                severity=SEVERITY_MODERATE,
                rationale=f"Agent {agent.agent_id} passed required checks with metadata warnings.",
                agent=agent,
                metadata={"warnings": warnings, "missing_fields": missing_fields},
            )
        return self._score(
            score_name="agent_output_contract",
            score_value=1.0,
            score_status=PASS,
            severity=SEVERITY_INFORMATIONAL,
            rationale=f"Agent {agent.agent_id} output satisfied deterministic contract checks.",
            agent=agent,
            metadata={"required_fields": sorted(required_output_fields)},
        )

    def _score(
        self,
        *,
        score_name: str,
        score_value: float,
        score_status: str,
        severity: str,
        rationale: str,
        agent: AgentExecutionEvidence | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvaluationScore:
        return EvaluationScore(
            evaluator_id=self.evaluator_id,
            evaluator_version=self.evaluator_version,
            score_name=score_name,
            score_value=score_value,
            score_status=score_status,
            severity=severity,
            rationale=rationale,
            agent_execution_id=agent.agent_execution_id if agent else None,
            prompt_id=agent.prompt_id if agent else None,
            prompt_version=agent.prompt_version if agent else None,
            model_name=agent.model_name if agent else None,
            result_metadata=metadata or {},
        )


class ToolUsageEvaluator:
    evaluator_id = "tool-usage-contract"
    evaluator_version = EVALUATOR_VERSION

    def evaluate(
        self,
        evidence: WorkflowEvaluationEvidence,
        expectations: EvaluationExpectations | None = None,
    ) -> list[EvaluationScore]:
        expectations = expectations or EvaluationExpectations()
        scores = [self._score_expected_tools(evidence, expectations)]
        scores.extend(self._score_tool(tool) for tool in evidence.tool_invocations)
        return scores

    def _score_expected_tools(
        self,
        evidence: WorkflowEvaluationEvidence,
        expectations: EvaluationExpectations,
    ) -> EvaluationScore:
        expected_tools = set(expectations.expected_tools)
        actual_tools = {tool.tool_id for tool in evidence.tool_invocations}
        missing_tools = sorted(expected_tools - actual_tools)
        unexpected_tools = sorted(actual_tools - expected_tools) if expected_tools else []

        if missing_tools:
            return self._score(
                score_name="expected_tool_coverage",
                score_value=0.0,
                score_status=FAIL,
                severity=SEVERITY_CRITICAL,
                rationale="Expected governed tool invocations were missing.",
                metadata={"missing_tools": missing_tools, "unexpected_tools": unexpected_tools},
            )
        if unexpected_tools:
            return self._score(
                score_name="expected_tool_coverage",
                score_value=0.75,
                score_status=WARN,
                severity=SEVERITY_MODERATE,
                rationale="Tool invocations included tools outside the expected local scenario.",
                metadata={"unexpected_tools": unexpected_tools, "actual_tools": sorted(actual_tools)},
            )
        return self._score(
            score_name="expected_tool_coverage",
            score_value=1.0,
            score_status=PASS,
            severity=SEVERITY_INFORMATIONAL,
            rationale="Expected governed tool invocations were present.",
            metadata={"actual_tools": sorted(actual_tools), "expected_tools": sorted(expected_tools)},
        )

    def _score_tool(self, tool: ToolInvocationEvidence) -> EvaluationScore:
        failures: list[str] = []
        if tool.status != "COMPLETED":
            failures.append("tool status was not COMPLETED")
        if tool.permission_status != "AUTHORIZED":
            failures.append("tool permission status was not AUTHORIZED")
        if tool.input_validation_status != "VALIDATED":
            failures.append("tool input validation status was not VALIDATED")
        if tool.output_validation_status != "VALIDATED":
            failures.append("tool output validation status was not VALIDATED")

        if failures:
            return self._score(
                score_name="tool_invocation_contract",
                score_value=0.0,
                score_status=FAIL,
                severity=SEVERITY_CRITICAL,
                rationale=f"Tool {tool.tool_id} failed deterministic invocation checks.",
                metadata={"tool_id": tool.tool_id, "failures": failures},
            )
        return self._score(
            score_name="tool_invocation_contract",
            score_value=1.0,
            score_status=PASS,
            severity=SEVERITY_INFORMATIONAL,
            rationale=f"Tool {tool.tool_id} satisfied deterministic invocation checks.",
            metadata={"tool_id": tool.tool_id, "agent_id": tool.agent_id},
        )

    def _score(
        self,
        *,
        score_name: str,
        score_value: float,
        score_status: str,
        severity: str,
        rationale: str,
        metadata: dict[str, Any] | None = None,
    ) -> EvaluationScore:
        return EvaluationScore(
            evaluator_id=self.evaluator_id,
            evaluator_version=self.evaluator_version,
            score_name=score_name,
            score_value=score_value,
            score_status=score_status,
            severity=severity,
            rationale=rationale,
            result_metadata=metadata or {},
        )


class EscalationEvaluator:
    evaluator_id = "human-review-escalation"
    evaluator_version = EVALUATOR_VERSION

    def evaluate(
        self,
        evidence: WorkflowEvaluationEvidence,
        expectations: EvaluationExpectations | None = None,
    ) -> list[EvaluationScore]:
        expectations = expectations or EvaluationExpectations()
        expected_human_review = expectations.expected_human_review
        agent_requires_review = any(agent.requires_human_review for agent in evidence.agent_executions)
        reviewable_or_completed = evidence.workflow_state in {"HUMAN_REVIEW_REQUIRED", "APPROVED", "REJECTED", "COMPLETED"}

        failures: list[str] = []
        warnings: list[str] = []
        if expected_human_review is True and not reviewable_or_completed:
            failures.append("workflow did not reach a human-review or terminal state")
        if expected_human_review is True and not agent_requires_review:
            warnings.append("no agent execution required human review for an expected review scenario")
        if expected_human_review is False and agent_requires_review:
            warnings.append("agent required human review in a scenario expected to avoid escalation")
        if expectations.expected_terminal_decision and evidence.approval_decision != expectations.expected_terminal_decision:
            failures.append("approval decision did not match expected terminal decision")

        if failures:
            return [
                self._score(
                    score_value=0.0,
                    score_status=FAIL,
                    severity=SEVERITY_CRITICAL,
                    rationale="Workflow escalation behavior failed deterministic checks.",
                    metadata={"failures": failures, "warnings": warnings},
                )
            ]
        if warnings:
            return [
                self._score(
                    score_value=0.75,
                    score_status=WARN,
                    severity=SEVERITY_MODERATE,
                    rationale="Workflow escalation behavior passed with warning signals.",
                    metadata={"warnings": warnings},
                )
            ]
        return [
            self._score(
                score_value=1.0,
                score_status=PASS,
                severity=SEVERITY_INFORMATIONAL,
                rationale="Workflow escalation behavior matched deterministic expectations.",
                metadata={
                    "workflow_state": evidence.workflow_state,
                    "agent_requires_human_review": agent_requires_review,
                    "expected_human_review": expected_human_review,
                },
            )
        ]

    def _score(
        self,
        *,
        score_value: float,
        score_status: str,
        severity: str,
        rationale: str,
        metadata: dict[str, Any] | None = None,
    ) -> EvaluationScore:
        return EvaluationScore(
            evaluator_id=self.evaluator_id,
            evaluator_version=self.evaluator_version,
            score_name="human_review_escalation",
            score_value=score_value,
            score_status=score_status,
            severity=severity,
            rationale=rationale,
            result_metadata=metadata or {},
        )


class HallucinationSignalEvaluator:
    evaluator_id = "evidence-consistency-signals"
    evaluator_version = EVALUATOR_VERSION

    def evaluate(
        self,
        evidence: WorkflowEvaluationEvidence,
        expectations: EvaluationExpectations | None = None,
    ) -> list[EvaluationScore]:
        del expectations
        claimed_tool_ids = _claimed_tool_ids(evidence.agent_executions)
        persisted_tool_ids = {tool.tool_id for tool in evidence.tool_invocations}
        unsupported_tool_claims = sorted(claimed_tool_ids - persisted_tool_ids)
        high_confidence_validation_failures = sorted(
            agent.agent_id
            for agent in evidence.agent_executions
            if agent.confidence_score >= 0.85 and agent.validation_status != "VALIDATED"
        )

        if unsupported_tool_claims:
            return [
                self._score(
                    score_value=0.0,
                    score_status=FAIL,
                    severity=SEVERITY_CRITICAL,
                    rationale="Agent telemetry claimed tool evidence that was not present in persisted tool records.",
                    metadata={
                        "unsupported_tool_claims": unsupported_tool_claims,
                        "persisted_tool_ids": sorted(persisted_tool_ids),
                    },
                )
            ]
        if high_confidence_validation_failures:
            return [
                self._score(
                    score_value=0.5,
                    score_status=WARN,
                    severity=SEVERITY_MODERATE,
                    rationale="High-confidence agent outputs had validation failures.",
                    metadata={"agent_ids": high_confidence_validation_failures},
                )
            ]
        return [
            self._score(
                score_value=1.0,
                score_status=PASS,
                severity=SEVERITY_INFORMATIONAL,
                rationale="No deterministic hallucination-like evidence consistency signals were detected.",
                metadata={
                    "claimed_tool_ids": sorted(claimed_tool_ids),
                    "persisted_tool_ids": sorted(persisted_tool_ids),
                },
            )
        ]

    def _score(
        self,
        *,
        score_value: float,
        score_status: str,
        severity: str,
        rationale: str,
        metadata: dict[str, Any] | None = None,
    ) -> EvaluationScore:
        return EvaluationScore(
            evaluator_id=self.evaluator_id,
            evaluator_version=self.evaluator_version,
            score_name="evidence_consistency_signal",
            score_value=score_value,
            score_status=score_status,
            severity=severity,
            rationale=rationale,
            result_metadata=metadata or {},
        )


def deterministic_evaluators() -> tuple[DeterministicEvaluator, ...]:
    return (
        AgentOutputEvaluator(),
        ToolUsageEvaluator(),
        EscalationEvaluator(),
        HallucinationSignalEvaluator(),
    )


def evaluate_deterministically(
    evidence: WorkflowEvaluationEvidence,
    expectations: EvaluationExpectations | None = None,
) -> list[EvaluationScore]:
    scores: list[EvaluationScore] = []
    for evaluator in deterministic_evaluators():
        scores.extend(evaluator.evaluate(evidence, expectations))
    return scores


def _claimed_tool_ids(agent_executions: tuple[AgentExecutionEvidence, ...]) -> set[str]:
    claimed_tool_ids: set[str] = set()
    for agent in agent_executions:
        for invocation in agent.execution_metadata.get("tool_invocations", []):
            if isinstance(invocation, dict) and invocation.get("tool_id"):
                claimed_tool_ids.add(str(invocation["tool_id"]))
    return claimed_tool_ids
