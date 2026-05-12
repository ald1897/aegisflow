from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from aegisflow_evaluation_service.models import (
    AgentExecutionRecord,
    Base,
    EvaluationRun,
    WorkflowRecord,
)
from aegisflow_evaluation_service.repository import EvaluationRepository
from aegisflow_evaluation_service.schemas import (
    EvaluationDatasetCaseCreate,
    EvaluationDatasetCaseRead,
    EvaluationResultCreate,
    EvaluationResultRead,
    EvaluationRunCreate,
    EvaluationRunRead,
)


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


async def seed_workflow(session: AsyncSession, workflow_id: UUID, agent_execution_id: UUID | None = None) -> None:
    session.add(WorkflowRecord(workflow_id=str(workflow_id)))
    if agent_execution_id is not None:
        session.add(AgentExecutionRecord(agent_execution_id=str(agent_execution_id)))
    await session.flush()


async def test_evaluation_run_and_result_can_be_persisted_and_read(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id = uuid4()
    agent_execution_id = uuid4()
    run_id = uuid4()
    result_id = uuid4()
    started_at = datetime.now(timezone.utc)

    async with session_factory() as session:
        await seed_workflow(session, workflow_id, agent_execution_id)
        repository = EvaluationRepository(session)

        run = await repository.create_run(
            EvaluationRunCreate(
                evaluation_run_id=run_id,
                workflow_id=workflow_id,
                correlation_id="phase7-ws2",
                evaluation_scope="workflow",
                evaluation_mode="deterministic_local",
                dataset_id="mortgage-exception-local-v1",
                status="COMPLETED",
                started_at=started_at,
                completed_at=started_at + timedelta(seconds=1),
                created_by="pytest",
                run_metadata={"source": "unit-test"},
            )
        )
        result = await repository.create_result(
            EvaluationResultCreate(
                evaluation_result_id=result_id,
                evaluation_run_id=run_id,
                workflow_id=workflow_id,
                agent_execution_id=agent_execution_id,
                prompt_id="intake-agent",
                prompt_version="v1",
                model_name="deterministic-langgraph-local-v1",
                evaluator_id="agent-output-contract",
                evaluator_version="v1",
                score_name="schema_validity",
                score_value=1.0,
                score_status="PASS",
                severity="informational",
                rationale="Agent output preserved the expected validated schema.",
                result_metadata={"bounded": True},
            )
        )
        await session.commit()

    async with session_factory() as session:
        repository = EvaluationRepository(session)
        persisted_run = await repository.get_run(str(run_id))
        persisted_results = await repository.list_results_for_run(str(run_id))

    assert run.evaluation_run_id == str(run_id)
    assert result.evaluation_result_id == str(result_id)
    assert persisted_run is not None
    assert EvaluationRunRead.model_validate(persisted_run).workflow_id == workflow_id
    assert len(persisted_results) == 1
    result_read = EvaluationResultRead.model_validate(persisted_results[0])
    assert result_read.agent_execution_id == agent_execution_id
    assert result_read.prompt_id == "intake-agent"
    assert result_read.score_status == "PASS"


async def test_create_run_is_idempotent_for_explicit_run_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id = uuid4()
    run_id = uuid4()
    started_at = datetime.now(timezone.utc)

    async with session_factory() as session:
        await seed_workflow(session, workflow_id)
        repository = EvaluationRepository(session)
        payload = EvaluationRunCreate(
            evaluation_run_id=run_id,
            workflow_id=workflow_id,
            correlation_id="phase7-ws2",
            evaluation_scope="workflow",
            evaluation_mode="deterministic_local",
            status="COMPLETED",
            started_at=started_at,
            created_by="pytest",
            run_metadata={"attempt": 1},
        )

        first = await repository.create_run(payload)
        second = await repository.create_run(
            payload.model_copy(update={"status": "FAILED", "run_metadata": {"attempt": 2}})
        )
        await session.commit()

        rows = (await session.execute(select(EvaluationRun))).scalars().all()

    assert first.evaluation_run_id == second.evaluation_run_id == str(run_id)
    assert second.status == "COMPLETED"
    assert second.run_metadata == {"attempt": 1}
    assert len(rows) == 1


async def test_runs_are_listed_by_workflow_in_started_order(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id = uuid4()
    first_run_id = uuid4()
    second_run_id = uuid4()
    started_at = datetime.now(timezone.utc)

    async with session_factory() as session:
        await seed_workflow(session, workflow_id)
        repository = EvaluationRepository(session)
        await repository.create_run(
            EvaluationRunCreate(
                evaluation_run_id=second_run_id,
                workflow_id=workflow_id,
                correlation_id="phase7-ws2",
                evaluation_scope="workflow",
                evaluation_mode="deterministic_local",
                status="COMPLETED",
                started_at=started_at + timedelta(minutes=1),
                created_by="pytest",
            )
        )
        await repository.create_run(
            EvaluationRunCreate(
                evaluation_run_id=first_run_id,
                workflow_id=workflow_id,
                correlation_id="phase7-ws2",
                evaluation_scope="workflow",
                evaluation_mode="dataset_replay",
                status="COMPLETED",
                started_at=started_at,
                created_by="pytest",
            )
        )
        await session.commit()

        runs = await repository.list_runs_for_workflow(str(workflow_id))

    assert [run.evaluation_run_id for run in runs] == [str(first_run_id), str(second_run_id)]


async def test_dataset_cases_can_be_persisted_and_filtered(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = EvaluationRepository(session)
        await repository.create_dataset_case(
            EvaluationDatasetCaseCreate(
                dataset_case_id="mortgage-exception-local-v1:approval",
                dataset_id="mortgage-exception-local-v1",
                case_name="approval",
                workflow_type="MORTGAGE_EXCEPTION_REVIEW",
                expected_agents={"agent_ids": ["intake_agent", "document_analysis_agent"]},
                expected_tools={"tool_ids": ["borrower_profile_lookup", "document_fetch"]},
                expected_human_review=True,
                expected_decision="APPROVED",
                expected_signals={"requires_human_review": True},
                case_metadata={"bounded": True},
            )
        )
        await repository.create_dataset_case(
            EvaluationDatasetCaseCreate(
                dataset_case_id="other-dataset:case",
                dataset_id="other-dataset",
                case_name="case",
                workflow_type="MORTGAGE_EXCEPTION_REVIEW",
                expected_human_review=True,
            )
        )
        await session.commit()

        cases = await repository.list_dataset_cases("mortgage-exception-local-v1")

    assert len(cases) == 1
    case_read = EvaluationDatasetCaseRead.model_validate(cases[0])
    assert case_read.dataset_case_id == "mortgage-exception-local-v1:approval"
    assert case_read.expected_decision == "APPROVED"
    assert case_read.expected_tools["tool_ids"] == ["borrower_profile_lookup", "document_fetch"]
