from collections.abc import AsyncIterator
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from aegisflow_evaluation_service.config import get_settings
from aegisflow_evaluation_service.database import dispose_engine, get_session
from aegisflow_evaluation_service.main import create_app
from aegisflow_evaluation_service.models import (
    AgentExecutionRecord,
    ApprovalRecord,
    Base,
    EvaluationResult,
    EvaluationRun,
    ToolInvocationRecord,
    WorkflowRecord,
    WorkflowTimelineEntry,
)


@pytest.fixture
async def session_factory(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite://")
    monkeypatch.setenv("ENABLE_TELEMETRY", "false")
    get_settings.cache_clear()
    await dispose_engine()

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    await engine.dispose()
    get_settings.cache_clear()
    await dispose_engine()


@pytest.fixture
async def client(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        yield async_client


async def seed_evaluable_workflow(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    workflow_id,
    state: str = "COMPLETED",
    include_agent: bool = True,
) -> None:
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        session.add(
            WorkflowRecord(
                workflow_id=str(workflow_id),
                workflow_type="MORTGAGE_EXCEPTION_REVIEW",
                state=state,
                priority="HIGH",
                correlation_id="phase7-ws5",
                created_by="pytest",
                workflow_metadata={"case_reference": "CASE-123"},
                started_at=now,
                completed_at=now if state == "COMPLETED" else None,
                created_at=now,
                updated_at=now,
            )
        )
        if include_agent:
            agent_execution_id = uuid4()
            session.add(
                AgentExecutionRecord(
                    agent_execution_id=str(agent_execution_id),
                    workflow_id=str(workflow_id),
                    agent_id="intake_agent",
                    prompt_id="intake-agent",
                    prompt_version="v1",
                    model_name="deterministic-langgraph-local-v1",
                    status="COMPLETED",
                    validation_status="VALIDATED",
                    confidence_score=0.91,
                    requires_human_review=True,
                    input_metadata={"bounded": True},
                    output_payload={
                        "recommended_next_state": "DOCUMENT_ANALYSIS_PENDING",
                        "summary": "Bounded evaluation orchestration test summary.",
                        "requires_human_review": True,
                        "confidence_score": 0.91,
                    },
                    execution_metadata={"tool_invocations": [{"tool_id": "borrower_profile_lookup"}]},
                    correlation_id="phase7-ws5",
                    created_by="pytest",
                    started_at=now,
                    completed_at=now,
                    created_at=now,
                )
            )
            session.add(
                ToolInvocationRecord(
                    tool_invocation_id=str(uuid4()),
                    workflow_id=str(workflow_id),
                    correlation_id="phase7-ws5",
                    agent_execution_id=str(agent_execution_id),
                    agent_id="intake_agent",
                    tool_id="borrower_profile_lookup",
                    status="COMPLETED",
                    permission_status="AUTHORIZED",
                    input_validation_status="VALIDATED",
                    output_validation_status="VALIDATED",
                    input_metadata={"bounded": True},
                    output_payload={"profile_status": "FOUND"},
                    execution_metadata={"source": "unit-test"},
                    created_by="pytest",
                    started_at=now,
                    completed_at=now,
                    created_at=now,
                )
            )
        session.add(
            WorkflowTimelineEntry(
                timeline_entry_id=str(uuid4()),
                workflow_id=str(workflow_id),
                entry_type="STATE_TRANSITION",
                message="Workflow reached human review or completion.",
                state=state,
                correlation_id="phase7-ws5",
                created_by="pytest",
                entry_metadata={"bounded": True},
                created_at=now,
            )
        )
        if state == "COMPLETED":
            session.add(
                ApprovalRecord(
                    approval_id=str(uuid4()),
                    workflow_id=str(workflow_id),
                    correlation_id="phase7-ws5",
                    decision="APPROVED",
                    decision_reason="LOCAL_VALIDATION",
                    comment="Bounded local approval comment.",
                    reviewed_by="pytest-reviewer",
                    reviewed_at=now,
                    approval_metadata={"bounded": True},
                    created_at=now,
                )
            )
        await session.commit()


async def test_create_workflow_evaluation_run_persists_deterministic_results(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id = uuid4()
    await seed_evaluable_workflow(session_factory, workflow_id=workflow_id)

    response = await client.post(
        f"/api/v1/evaluations/workflows/{workflow_id}/runs",
        headers={"X-Actor-ID": "pytest-evaluator"},
        json={
            "expected_agents": ["intake_agent"],
            "expected_tools": ["borrower_profile_lookup"],
            "expected_human_review": True,
            "expected_terminal_decision": "APPROVED",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["run"]["workflow_id"] == str(workflow_id)
    assert payload["run"]["status"] == "COMPLETED"
    assert payload["run"]["created_by"] == "pytest-evaluator"
    evaluator_ids = {result["evaluator_id"] for result in payload["results"]}
    assert evaluator_ids == {
        "agent-output-contract",
        "tool-usage-contract",
        "human-review-escalation",
        "evidence-consistency-signals",
    }

    async with session_factory() as session:
        runs = (await session.execute(select(EvaluationRun))).scalars().all()
        results = (await session.execute(select(EvaluationResult))).scalars().all()

    assert len(runs) == 1
    assert len(results) == len(payload["results"])


async def test_judge_model_disabled_mode_includes_judge_boundary_result(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id = uuid4()
    await seed_evaluable_workflow(session_factory, workflow_id=workflow_id)

    response = await client.post(
        f"/api/v1/evaluations/workflows/{workflow_id}/runs",
        json={
            "evaluation_mode": "judge_model_disabled",
            "expected_tools": ["borrower_profile_lookup"],
            "expected_human_review": True,
            "expected_terminal_decision": "APPROVED",
        },
    )

    assert response.status_code == 201
    evaluator_ids = {result["evaluator_id"] for result in response.json()["results"]}
    assert "judge-model-boundary" in evaluator_ids


async def test_evaluation_run_creation_is_idempotent_for_explicit_run_id(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id = uuid4()
    run_id = uuid4()
    await seed_evaluable_workflow(session_factory, workflow_id=workflow_id)

    request_body = {
        "evaluation_run_id": str(run_id),
        "expected_tools": ["borrower_profile_lookup"],
        "expected_human_review": True,
    }
    first = await client.post(f"/api/v1/evaluations/workflows/{workflow_id}/runs", json=request_body)
    second = await client.post(f"/api/v1/evaluations/workflows/{workflow_id}/runs", json=request_body)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["run"]["evaluation_run_id"] == second.json()["run"]["evaluation_run_id"] == str(run_id)

    async with session_factory() as session:
        runs = (await session.execute(select(EvaluationRun))).scalars().all()

    assert len(runs) == 1


async def test_get_and_list_evaluation_runs(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id = uuid4()
    await seed_evaluable_workflow(session_factory, workflow_id=workflow_id)
    create_response = await client.post(f"/api/v1/evaluations/workflows/{workflow_id}/runs", json={})
    run_id = create_response.json()["run"]["evaluation_run_id"]

    get_response = await client.get(f"/api/v1/evaluations/runs/{run_id}")
    list_response = await client.get(f"/api/v1/evaluations/workflows/{workflow_id}/runs")

    assert get_response.status_code == 200
    assert get_response.json()["run"]["evaluation_run_id"] == run_id
    assert list_response.status_code == 200
    assert list_response.json()[0]["evaluation_run_id"] == run_id
    assert list_response.json()[0]["result_count"] == len(get_response.json()["results"])


async def test_missing_workflow_returns_structured_error(client: AsyncClient) -> None:
    workflow_id = uuid4()

    response = await client.post(f"/api/v1/evaluations/workflows/{workflow_id}/runs", json={})

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "workflow_not_found"


async def test_incomplete_workflow_returns_structured_error(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id = uuid4()
    await seed_evaluable_workflow(session_factory, workflow_id=workflow_id, state="NEW", include_agent=False)

    response = await client.post(f"/api/v1/evaluations/workflows/{workflow_id}/runs", json={})

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "workflow_not_ready_for_evaluation"
