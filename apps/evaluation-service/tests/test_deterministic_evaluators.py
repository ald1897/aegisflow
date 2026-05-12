from aegisflow_evaluation_service.evaluators import (
    FAIL,
    PASS,
    WARN,
    AgentOutputEvaluator,
    EscalationEvaluator,
    HallucinationSignalEvaluator,
    ToolUsageEvaluator,
    evaluate_deterministically,
)
from aegisflow_evaluation_service.evidence import (
    AgentExecutionEvidence,
    EvaluationExpectations,
    ToolInvocationEvidence,
    WorkflowEvaluationEvidence,
)


def agent_evidence(
    *,
    agent_id: str = "intake_agent",
    agent_execution_id: str = "agent-execution-1",
    validation_status: str = "VALIDATED",
    confidence_score: float = 0.91,
    requires_human_review: bool = True,
    output_overrides: dict | None = None,
    metadata_overrides: dict | None = None,
) -> AgentExecutionEvidence:
    output = {
        "recommended_next_state": "DOCUMENT_ANALYSIS_PENDING",
        "summary": "Governed local evaluation summary.",
        "requires_human_review": requires_human_review,
        "confidence_score": confidence_score,
    }
    output.update(output_overrides or {})
    metadata = {
        "tool_invocations": [
            {
                "tool_id": "borrower_profile_lookup",
                "status": "COMPLETED",
            }
        ]
    }
    metadata.update(metadata_overrides or {})
    return AgentExecutionEvidence(
        agent_execution_id=agent_execution_id,
        agent_id=agent_id,
        prompt_id="intake-agent",
        prompt_version="v1",
        model_name="deterministic-langgraph-local-v1",
        status="COMPLETED",
        validation_status=validation_status,
        confidence_score=confidence_score,
        requires_human_review=requires_human_review,
        output_payload=output,
        execution_metadata=metadata,
    )


def tool_evidence(
    *,
    tool_id: str = "borrower_profile_lookup",
    status: str = "COMPLETED",
    permission_status: str = "AUTHORIZED",
    input_validation_status: str = "VALIDATED",
    output_validation_status: str = "VALIDATED",
) -> ToolInvocationEvidence:
    return ToolInvocationEvidence(
        tool_invocation_id="tool-invocation-1",
        agent_execution_id="agent-execution-1",
        agent_id="intake_agent",
        tool_id=tool_id,
        status=status,
        permission_status=permission_status,
        input_validation_status=input_validation_status,
        output_validation_status=output_validation_status,
        output_payload={"profile_status": "FOUND"},
    )


def workflow_evidence(
    *,
    agent: AgentExecutionEvidence | None = None,
    tool: ToolInvocationEvidence | None = None,
    workflow_state: str = "HUMAN_REVIEW_REQUIRED",
    approval_decision: str | None = None,
) -> WorkflowEvaluationEvidence:
    return WorkflowEvaluationEvidence(
        workflow_id="workflow-1",
        workflow_type="MORTGAGE_EXCEPTION_REVIEW",
        workflow_state=workflow_state,
        correlation_id="correlation-1",
        agent_executions=(agent or agent_evidence(),),
        tool_invocations=(tool or tool_evidence(),),
        approval_decision=approval_decision,
    )


def test_agent_output_evaluator_passes_valid_agent_contract() -> None:
    scores = AgentOutputEvaluator().evaluate(workflow_evidence())

    assert len(scores) == 1
    assert scores[0].evaluator_id == "agent-output-contract"
    assert scores[0].score_status == PASS
    assert scores[0].score_value == 1.0
    assert scores[0].agent_execution_id == "agent-execution-1"
    assert scores[0].prompt_id == "intake-agent"


def test_agent_output_evaluator_warns_on_metadata_mismatch() -> None:
    agent = agent_evidence(output_overrides={"confidence_score": 0.5})

    scores = AgentOutputEvaluator().evaluate(workflow_evidence(agent=agent))

    assert scores[0].score_status == WARN
    assert scores[0].severity == "moderate"
    assert "warnings" in scores[0].result_metadata


def test_agent_output_evaluator_fails_missing_required_fields() -> None:
    agent = agent_evidence(output_overrides={"summary": None})
    output = dict(agent.output_payload)
    output.pop("recommended_next_state")
    agent = AgentExecutionEvidence(
        **{
            **agent.__dict__,
            "validation_status": "REJECTED",
            "output_payload": output,
        }
    )

    scores = AgentOutputEvaluator().evaluate(workflow_evidence(agent=agent))

    assert scores[0].score_status == FAIL
    assert scores[0].severity == "critical"
    assert "recommended_next_state" in scores[0].result_metadata["missing_fields"]


def test_tool_usage_evaluator_scores_expected_tools_and_invocation_contract() -> None:
    scores = ToolUsageEvaluator().evaluate(
        workflow_evidence(),
        EvaluationExpectations(expected_tools=("borrower_profile_lookup",)),
    )

    assert [score.score_status for score in scores] == [PASS, PASS]
    assert scores[0].score_name == "expected_tool_coverage"
    assert scores[1].score_name == "tool_invocation_contract"


def test_tool_usage_evaluator_fails_missing_expected_tool() -> None:
    scores = ToolUsageEvaluator().evaluate(
        workflow_evidence(),
        EvaluationExpectations(expected_tools=("document_fetch",)),
    )

    assert scores[0].score_status == FAIL
    assert scores[0].result_metadata["missing_tools"] == ["document_fetch"]


def test_tool_usage_evaluator_fails_invalid_tool_invocation() -> None:
    tool = tool_evidence(permission_status="DENIED")

    scores = ToolUsageEvaluator().evaluate(workflow_evidence(tool=tool))
    invocation_score = next(score for score in scores if score.score_name == "tool_invocation_contract")

    assert invocation_score.score_status == FAIL
    assert "tool permission status was not AUTHORIZED" in invocation_score.result_metadata["failures"]


def test_escalation_evaluator_passes_expected_human_review_path() -> None:
    scores = EscalationEvaluator().evaluate(
        workflow_evidence(approval_decision="APPROVED", workflow_state="COMPLETED"),
        EvaluationExpectations(expected_human_review=True, expected_terminal_decision="APPROVED"),
    )

    assert scores[0].score_status == PASS
    assert scores[0].score_name == "human_review_escalation"


def test_escalation_evaluator_warns_when_agent_review_signal_is_missing() -> None:
    agent = agent_evidence(requires_human_review=False, output_overrides={"requires_human_review": False})

    scores = EscalationEvaluator().evaluate(
        workflow_evidence(agent=agent),
        EvaluationExpectations(expected_human_review=True),
    )

    assert scores[0].score_status == WARN
    assert "warnings" in scores[0].result_metadata


def test_escalation_evaluator_fails_unexpected_terminal_decision() -> None:
    scores = EscalationEvaluator().evaluate(
        workflow_evidence(approval_decision="REJECTED", workflow_state="COMPLETED"),
        EvaluationExpectations(expected_human_review=True, expected_terminal_decision="APPROVED"),
    )

    assert scores[0].score_status == FAIL
    assert "approval decision did not match expected terminal decision" in scores[0].result_metadata["failures"]


def test_hallucination_signal_evaluator_passes_consistent_tool_evidence() -> None:
    scores = HallucinationSignalEvaluator().evaluate(workflow_evidence())

    assert scores[0].score_status == PASS
    assert scores[0].result_metadata["claimed_tool_ids"] == ["borrower_profile_lookup"]


def test_hallucination_signal_evaluator_fails_unsupported_tool_claim() -> None:
    agent = agent_evidence(metadata_overrides={"tool_invocations": [{"tool_id": "fabricated_tool"}]})

    scores = HallucinationSignalEvaluator().evaluate(workflow_evidence(agent=agent))

    assert scores[0].score_status == FAIL
    assert scores[0].result_metadata["unsupported_tool_claims"] == ["fabricated_tool"]


def test_hallucination_signal_evaluator_warns_high_confidence_validation_failure() -> None:
    agent = agent_evidence(validation_status="REJECTED", confidence_score=0.95)

    scores = HallucinationSignalEvaluator().evaluate(workflow_evidence(agent=agent))

    assert scores[0].score_status == WARN
    assert scores[0].result_metadata["agent_ids"] == ["intake_agent"]


def test_evaluate_deterministically_runs_all_local_evaluators() -> None:
    scores = evaluate_deterministically(
        workflow_evidence(approval_decision="APPROVED", workflow_state="COMPLETED"),
        EvaluationExpectations(
            expected_tools=("borrower_profile_lookup",),
            expected_human_review=True,
            expected_terminal_decision="APPROVED",
        ),
    )

    evaluator_ids = {score.evaluator_id for score in scores}
    assert evaluator_ids == {
        "agent-output-contract",
        "tool-usage-contract",
        "human-review-escalation",
        "evidence-consistency-signals",
    }
    assert all(score.rationale for score in scores)
    assert all(score.result_metadata is not None for score in scores)
