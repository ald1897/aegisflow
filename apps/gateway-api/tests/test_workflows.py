from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from aegisflow_gateway.main import create_app
from aegisflow_gateway.persistence.database import get_session
from aegisflow_gateway.persistence.models import (
    AgentExecutionRecord,
    Base,
    ToolInvocationRecord,
    WorkflowEventOutbox,
    WorkflowRecord,
    WorkflowStateTransition,
    WorkflowTimelineEntry,
)
from aegisflow_gateway.persistence.models import utc_now


@pytest.fixture
async def app_context() -> AsyncIterator[tuple[object, async_sessionmaker[AsyncSession]]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    yield app, session_factory

    await engine.dispose()


@pytest.fixture
async def client(app_context: tuple[object, async_sessionmaker[AsyncSession]]) -> AsyncIterator[AsyncClient]:
    app, _ = app_context
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        yield async_client


async def test_health_returns_service_status(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-correlation-id"]


async def test_create_workflow_persists_new_workflow_and_transition(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "phase-1-test", "X-Actor-ID": "tester"},
        json={
            "workflow_type": "MORTGAGE_EXCEPTION_REVIEW",
            "priority": "HIGH",
            "metadata": {"case_reference": "MORT-123"},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert UUID(body["workflow_id"])
    assert body["state"] == "NEW"
    assert body["priority"] == "HIGH"
    assert body["correlation_id"] == "phase-1-test"
    assert body["metadata"] == {"case_reference": "MORT-123"}
    assert response.headers["x-correlation-id"] == "phase-1-test"

    _, session_factory = app_context
    async with session_factory() as session:
        workflow_count = len((await session.execute(select(WorkflowRecord))).scalars().all())
        transition = (await session.execute(select(WorkflowStateTransition))).scalar_one()
        timeline_entry = (await session.execute(select(WorkflowTimelineEntry))).scalar_one()
        outbox_event = (await session.execute(select(WorkflowEventOutbox))).scalar_one()

    assert workflow_count == 1
    assert transition.prior_state is None
    assert transition.new_state == "NEW"
    assert transition.transition_reason == "workflow_created"
    assert transition.created_by == "tester"
    assert timeline_entry.entry_type == "WORKFLOW_CREATED"
    assert timeline_entry.state == "NEW"
    assert timeline_entry.correlation_id == "phase-1-test"
    assert outbox_event.event_type == "workflow.created"
    assert outbox_event.publish_status == "PENDING"


async def test_get_workflow_returns_persisted_state(client: AsyncClient) -> None:
    create_response = await client.post("/api/v1/workflows", json={})
    workflow_id = create_response.json()["workflow_id"]

    get_response = await client.get(f"/api/v1/workflows/{workflow_id}")

    assert get_response.status_code == 200
    assert get_response.json()["workflow_id"] == workflow_id
    assert get_response.json()["workflow_type"] == "MORTGAGE_EXCEPTION_REVIEW"
    assert get_response.json()["state"] == "NEW"


async def test_get_workflow_returns_structured_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/workflows/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json()["error"] == "workflow_not_found"
    assert response.json()["correlation_id"] == response.headers["x-correlation-id"]


async def test_correlation_id_is_generated_when_missing(client: AsyncClient) -> None:
    response = await client.post("/api/v1/workflows", json={})

    assert response.status_code == 201
    assert response.headers["x-correlation-id"]
    assert response.json()["correlation_id"] == response.headers["x-correlation-id"]


async def test_get_workflow_timeline_returns_ordered_entries(client: AsyncClient) -> None:
    create_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "timeline-test"},
        json={},
    )
    workflow_id = create_response.json()["workflow_id"]

    response = await client.get(f"/api/v1/workflows/{workflow_id}/timeline")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_id"] == workflow_id
    assert len(body["entries"]) == 1
    assert body["entries"][0]["entry_type"] == "WORKFLOW_CREATED"
    assert body["entries"][0]["state"] == "NEW"
    assert body["entries"][0]["correlation_id"] == "timeline-test"


async def test_get_workflow_agent_executions_returns_persisted_records(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    create_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "agent-test"},
        json={},
    )
    workflow_id = create_response.json()["workflow_id"]

    _, session_factory = app_context
    now = utc_now()
    async with session_factory() as session:
        session.add(
            AgentExecutionRecord(
                agent_execution_id="00000000-0000-0000-0000-000000000001",
                workflow_id=workflow_id,
                agent_id="intake_agent",
                prompt_id="intake-agent",
                prompt_version="1",
                model_name="deterministic-langgraph-local-v1",
                status="COMPLETED",
                validation_status="VALIDATED",
                confidence_score=0.91,
                requires_human_review=False,
                input_metadata={"workflow_id": workflow_id},
                output_payload={"recommended_next_state": "DOCUMENT_ANALYSIS_PENDING"},
                execution_metadata={"workflow_state": "INTAKE_IN_PROGRESS"},
                error_message=None,
                correlation_id="agent-test",
                created_by="workflow-engine",
                started_at=now,
                completed_at=now,
                created_at=now,
            )
        )
        await session.commit()

    response = await client.get(f"/api/v1/workflows/{workflow_id}/agent-executions")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_id"] == workflow_id
    assert len(body["executions"]) == 1
    assert body["executions"][0]["agent_id"] == "intake_agent"
    assert body["executions"][0]["validation_status"] == "VALIDATED"


async def test_get_workflow_tool_invocations_returns_persisted_records(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    create_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "tool-query-test"},
        json={},
    )
    workflow_id = create_response.json()["workflow_id"]

    _, session_factory = app_context
    now = utc_now()
    async with session_factory() as session:
        session.add(
            ToolInvocationRecord(
                tool_invocation_id="00000000-0000-0000-0000-000000000002",
                workflow_id=workflow_id,
                correlation_id="tool-query-test",
                agent_execution_id=None,
                agent_id="intake_agent",
                tool_id="borrower_profile_lookup",
                status="COMPLETED",
                permission_status="AUTHORIZED",
                input_validation_status="VALIDATED",
                output_validation_status="VALIDATED",
                input_metadata={"case_reference_present": True},
                output_payload={"profile_status": "FOUND"},
                execution_metadata={"replay_safe": True},
                error_message=None,
                created_by="workflow-engine",
                started_at=now,
                completed_at=now,
                created_at=now,
            )
        )
        await session.commit()

    response = await client.get(f"/api/v1/workflows/{workflow_id}/tool-invocations")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_id"] == workflow_id
    assert len(body["invocations"]) == 1
    assert body["invocations"][0]["tool_id"] == "borrower_profile_lookup"
    assert body["invocations"][0]["permission_status"] == "AUTHORIZED"
    assert body["invocations"][0]["input_validation_status"] == "VALIDATED"
    assert body["invocations"][0]["output_validation_status"] == "VALIDATED"
    assert body["invocations"][0]["output"] == {"profile_status": "FOUND"}
    assert body["invocations"][0]["metadata"] == {"replay_safe": True}


async def test_get_workflow_tool_invocations_returns_structured_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/workflows/00000000-0000-0000-0000-000000000000/tool-invocations")

    assert response.status_code == 404
    assert response.json()["error"] == "workflow_not_found"
