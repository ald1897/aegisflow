from dataclasses import dataclass, field
from typing import Any, Protocol

from aegisflow_evaluation_service.config import Settings
from aegisflow_evaluation_service.evaluators import (
    FAIL,
    PASS,
    SEVERITY_CRITICAL,
    SEVERITY_INFORMATIONAL,
    SEVERITY_MODERATE,
    WARN,
    EvaluationScore,
)
from aegisflow_evaluation_service.evidence import EvaluationExpectations, WorkflowEvaluationEvidence

JUDGE_EVALUATOR_ID = "judge-model-boundary"
JUDGE_EVALUATOR_VERSION = "v1"
DEFAULT_RUBRIC_ID = "mortgage-exception-review-quality"
DEFAULT_RUBRIC_VERSION = "v1"


@dataclass(frozen=True)
class JudgeRubric:
    rubric_id: str
    rubric_version: str
    dimensions: tuple[str, ...] = (
        "factual_consistency",
        "operational_completeness",
        "governance_alignment",
    )


@dataclass(frozen=True)
class JudgeEvaluationRequest:
    evidence: WorkflowEvaluationEvidence
    expectations: EvaluationExpectations | None = None
    rubric: JudgeRubric = field(
        default_factory=lambda: JudgeRubric(
            rubric_id=DEFAULT_RUBRIC_ID,
            rubric_version=DEFAULT_RUBRIC_VERSION,
        )
    )


@dataclass(frozen=True)
class JudgeEvaluationResult:
    evaluator_id: str
    evaluator_version: str
    rubric_id: str
    rubric_version: str
    score_name: str
    score_value: float
    score_status: str
    severity: str
    rationale: str
    result_metadata: dict[str, Any] = field(default_factory=dict)

    def to_evaluation_score(self) -> EvaluationScore:
        return EvaluationScore(
            evaluator_id=self.evaluator_id,
            evaluator_version=self.evaluator_version,
            score_name=self.score_name,
            score_value=self.score_value,
            score_status=self.score_status,
            severity=self.severity,
            rationale=self.rationale,
            result_metadata={
                **self.result_metadata,
                "rubric_id": self.rubric_id,
                "rubric_version": self.rubric_version,
            },
        )


class JudgeEvaluator(Protocol):
    evaluator_id: str
    evaluator_version: str

    def evaluate(self, request: JudgeEvaluationRequest) -> JudgeEvaluationResult:
        ...


class ExternalJudgeModelDisabledError(RuntimeError):
    pass


class DeterministicLocalJudge:
    evaluator_id = JUDGE_EVALUATOR_ID
    evaluator_version = JUDGE_EVALUATOR_VERSION

    def evaluate(self, request: JudgeEvaluationRequest) -> JudgeEvaluationResult:
        evidence = request.evidence
        expectations = request.expectations or EvaluationExpectations()
        failures: list[str] = []
        warnings: list[str] = []

        if not evidence.agent_executions:
            failures.append("no agent executions were available for judge-style scoring")

        invalid_agents = sorted(
            agent.agent_id
            for agent in evidence.agent_executions
            if agent.status != "COMPLETED" or agent.validation_status != "VALIDATED"
        )
        if invalid_agents:
            failures.append("agent executions failed completion or validation checks")

        invalid_tools = sorted(
            tool.tool_id
            for tool in evidence.tool_invocations
            if (
                tool.status != "COMPLETED"
                or tool.permission_status != "AUTHORIZED"
                or tool.input_validation_status != "VALIDATED"
                or tool.output_validation_status != "VALIDATED"
            )
        )
        if invalid_tools:
            failures.append("tool invocations failed governed execution checks")

        if expectations.expected_human_review is True and evidence.workflow_state not in {
            "HUMAN_REVIEW_REQUIRED",
            "APPROVED",
            "REJECTED",
            "COMPLETED",
        }:
            failures.append("workflow did not reach the expected human review path")

        if expectations.expected_terminal_decision and evidence.approval_decision != expectations.expected_terminal_decision:
            failures.append("terminal approval decision did not match expectation")

        if expectations.expected_agents:
            observed_agents = {agent.agent_id for agent in evidence.agent_executions}
            missing_agents = sorted(set(expectations.expected_agents) - observed_agents)
            if missing_agents:
                warnings.append("expected agents were not present in workflow evidence")
        else:
            missing_agents = []

        if expectations.expected_tools:
            observed_tools = {tool.tool_id for tool in evidence.tool_invocations}
            missing_tools = sorted(set(expectations.expected_tools) - observed_tools)
            if missing_tools:
                warnings.append("expected tools were not present in workflow evidence")
        else:
            missing_tools = []

        metadata = {
            "judge_mode": "deterministic_local_fallback",
            "rubric_dimensions": list(request.rubric.dimensions),
            "agent_execution_count": len(evidence.agent_executions),
            "tool_invocation_count": len(evidence.tool_invocations),
            "invalid_agents": invalid_agents,
            "invalid_tools": invalid_tools,
            "missing_agents": missing_agents,
            "missing_tools": missing_tools,
        }

        if failures:
            return self._result(
                request=request,
                score_value=0.0,
                score_status=FAIL,
                severity=SEVERITY_CRITICAL,
                rationale="Deterministic judge fallback found critical evidence contract failures.",
                metadata={**metadata, "failures": failures, "warnings": warnings},
            )
        if warnings:
            return self._result(
                request=request,
                score_value=0.75,
                score_status=WARN,
                severity=SEVERITY_MODERATE,
                rationale="Deterministic judge fallback found bounded quality warning signals.",
                metadata={**metadata, "warnings": warnings},
            )
        return self._result(
            request=request,
            score_value=1.0,
            score_status=PASS,
            severity=SEVERITY_INFORMATIONAL,
            rationale="Deterministic judge fallback found workflow evidence aligned with the local rubric.",
            metadata=metadata,
        )

    def _result(
        self,
        *,
        request: JudgeEvaluationRequest,
        score_value: float,
        score_status: str,
        severity: str,
        rationale: str,
        metadata: dict[str, Any],
    ) -> JudgeEvaluationResult:
        return JudgeEvaluationResult(
            evaluator_id=self.evaluator_id,
            evaluator_version=self.evaluator_version,
            rubric_id=request.rubric.rubric_id,
            rubric_version=request.rubric.rubric_version,
            score_name="judge_quality_assessment",
            score_value=score_value,
            score_status=score_status,
            severity=severity,
            rationale=rationale,
            result_metadata=metadata,
        )


class ExternalJudgeModelBoundary:
    evaluator_id = JUDGE_EVALUATOR_ID
    evaluator_version = JUDGE_EVALUATOR_VERSION

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def evaluate(self, request: JudgeEvaluationRequest) -> JudgeEvaluationResult:
        del request
        if not self.settings.enable_external_judge_model:
            raise ExternalJudgeModelDisabledError("external judge model evaluation is disabled")
        raise NotImplementedError("external judge model providers are future work")


def get_judge_evaluator(settings: Settings) -> JudgeEvaluator:
    if settings.enable_external_judge_model:
        return ExternalJudgeModelBoundary(settings)
    return DeterministicLocalJudge()
