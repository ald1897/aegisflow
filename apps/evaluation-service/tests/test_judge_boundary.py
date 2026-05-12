from collections.abc import AsyncIterator
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from aegisflow_evaluation_service.config import Settings
from aegisflow_evaluation_service.evidence import (
    AgentExecutionEvidence,
    EvaluationExpectations,
    ToolInvocationEvidence,
    WorkflowEvaluationEvidence,
)
from aegisflow_evaluation_service.judges import (
    ExternalJudgeModelBoundary,
    ExternalJudgeModelDisabledError,
    JudgeEvaluationRequest,
    DeterministicLocalJudge,
    get_judge_evaluator,
)
from aegisflow_evaluation_service.models import Base, EvaluationRun, WorkflowRecord
from aegisflow_evaluation_service.repository import EvaluationRepository
from aegisflow_evaluation_service.schemas import EvaluationResultCreate, EvaluationResultRead, EvaluationRunCreate


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    await engine.dispose()


def agent_evidence(
    *,
    validation_status: str = "VALIDATED",
    status: str = "COMPLETED",
) -> AgentExecutionEvidence:
    return AgentExecutionEvidence(
        agent_execution_id=str(uuid4()),
        agent_id="intake_agent",
        prompt_id="intake-agent",
        prompt_version="v1",
        model_name="deterministic-langgraph-local-v1",
        status=status,
        validation_status=validation_status,
        confidence_score=0.9,
        requires_human_review=True,
        output_payload={
            "recommended_next_state": "DOCUMENT_ANALYSIS_PENDING",
            "summary": "Bounded local judge test summary.",
            "requires_human_review": True,
            "confidence_score": 0.9,
        },
        execution_metadata={"tool_invocations": [{"tool_id": "borrower_profile_lookup"}]},
    )


def tool_evidence() -> ToolInvocationEvidence:
    return ToolInvocationEvidence(
        tool_invocation_id=str(uuid4()),
        agent_execution_id=None,
        agent_id="intake_agent",
        tool_id="borrower_profile_lookup",
        status="COMPLETED",
        permission_status="AUTHORIZED",
        input_validation_status="VALIDATED",
        output_validation_status="VALIDATED",
    )


def workflow_evidence(
    workflow_id: UUID | None = None,
    *,
    agent: AgentExecutionEvidence | None = None,
    approval_decision: str | None = "APPROVED",
) -> WorkflowEvaluationEvidence:
    return WorkflowEvaluationEvidence(
        workflow_id=str(workflow_id or uuid4()),
        workflow_type="MORTGAGE_EXCEPTION_REVIEW",
        workflow_state="COMPLETED",
        correlation_id="phase7-ws4",
        agent_executions=(agent or agent_evidence(),),
        tool_invocations=(tool_evidence(),),
        approval_decision=approval_decision,
    )


def test_external_judge_model_is_disabled_by_default() -> None:
    settings = Settings()

    assert settings.enable_external_judge_model is False
    assert isinstance(get_judge_evaluator(settings), DeterministicLocalJudge)


def test_disabled_external_boundary_does_not_call_provider() -> None:
    boundary = ExternalJudgeModelBoundary(Settings(enable_external_judge_model=False))

    with pytest.raises(ExternalJudgeModelDisabledError):
        boundary.evaluate(JudgeEvaluationRequest(evidence=workflow_evidence()))


def test_deterministic_local_judge_passes_bounded_evidence() -> None:
    result = DeterministicLocalJudge().evaluate(
        JudgeEvaluationRequest(
            evidence=workflow_evidence(),
            expectations=EvaluationExpectations(
                expected_agents=("intake_agent",),
                expected_tools=("borrower_profile_lookup",),
                expected_human_review=True,
                expected_terminal_decision="APPROVED",
            ),
        )
    )

    assert result.evaluator_id == "judge-model-boundary"
    assert result.evaluator_version == "v1"
    assert result.rubric_id == "mortgage-exception-review-quality"
    assert result.score_name == "judge_quality_assessment"
    assert result.score_status == "PASS"
    assert result.score_value == 1.0
    assert result.result_metadata["judge_mode"] == "deterministic_local_fallback"
    assert "raw_output" not in result.result_metadata


def test_deterministic_local_judge_warns_on_missing_expected_evidence() -> None:
    result = DeterministicLocalJudge().evaluate(
        JudgeEvaluationRequest(
            evidence=workflow_evidence(),
            expectations=EvaluationExpectations(expected_tools=("document_fetch",)),
        )
    )

    assert result.score_status == "WARN"
    assert result.severity == "moderate"
    assert result.result_metadata["missing_tools"] == ["document_fetch"]


def test_deterministic_local_judge_fails_invalid_agent_contract() -> None:
    result = DeterministicLocalJudge().evaluate(
        JudgeEvaluationRequest(evidence=workflow_evidence(agent=agent_evidence(validation_status="REJECTED")))
    )

    assert result.score_status == "FAIL"
    assert result.severity == "critical"
    assert "agent executions failed completion or validation checks" in result.result_metadata["failures"]


async def test_judge_result_can_be_persisted_through_existing_result_contract(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id = uuid4()
    run_id = uuid4()
    result_id = uuid4()
    started_at = datetime.now(timezone.utc)

    judge_result = DeterministicLocalJudge().evaluate(JudgeEvaluationRequest(evidence=workflow_evidence(workflow_id)))
    score = judge_result.to_evaluation_score()

    async with session_factory() as session:
        session.add(WorkflowRecord(workflow_id=str(workflow_id)))
        repository = EvaluationRepository(session)
        await repository.create_run(
            EvaluationRunCreate(
                evaluation_run_id=run_id,
                workflow_id=workflow_id,
                correlation_id="phase7-ws4",
                evaluation_scope="workflow",
                evaluation_mode="judge_model_disabled",
                status="COMPLETED",
                started_at=started_at,
                completed_at=started_at,
                created_by="pytest",
                run_metadata={"judge_boundary": "deterministic_local"},
            )
        )
        await repository.create_result(
            EvaluationResultCreate(
                evaluation_result_id=result_id,
                evaluation_run_id=run_id,
                workflow_id=workflow_id,
                evaluator_id=score.evaluator_id,
                evaluator_version=score.evaluator_version,
                score_name=score.score_name,
                score_value=score.score_value,
                score_status=score.score_status,
                severity=score.severity,
                rationale=score.rationale,
                result_metadata=score.result_metadata,
            )
        )
        await session.commit()

    async with session_factory() as session:
        persisted_run = await session.get(EvaluationRun, str(run_id))
        persisted_results = await EvaluationRepository(session).list_results_for_run(str(run_id))

    assert persisted_run is not None
    assert len(persisted_results) == 1
    read_result = EvaluationResultRead.model_validate(persisted_results[0])
    assert read_result.evaluator_id == "judge-model-boundary"
    assert read_result.result_metadata["rubric_id"] == "mortgage-exception-review-quality"
    assert read_result.result_metadata["judge_mode"] == "deterministic_local_fallback"
