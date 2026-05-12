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
    ApprovalRecord,
    Base,
    EvaluationResult,
    EvaluationRun,
    ToolInvocationRecord,
    WorkflowEventOutbox,
    WorkflowRecord,
    WorkflowStateTransition,
    WorkflowTimelineEntry,
)
from aegisflow_gateway.persistence.models import utc_now
from aegisflow_gateway.services.temporal import TemporalWorkflowStarter


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


async def test_metrics_endpoint_exposes_gateway_metrics(client: AsyncClient) -> None:
    await client.get("/health")

    response = await client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "aegisflow_gateway_http_requests_total" in response.text


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


async def test_get_human_review_queue_returns_reviewable_workflows(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    review_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "review-queue-test"},
        json={"priority": "HIGH", "metadata": {"case_reference": "MORT-REVIEW"}},
    )
    completed_response = await client.post("/api/v1/workflows", json={})
    review_workflow_id = review_response.json()["workflow_id"]
    completed_workflow_id = completed_response.json()["workflow_id"]

    _, session_factory = app_context
    async with session_factory() as session:
        review_workflow = await session.get(WorkflowRecord, review_workflow_id)
        completed_workflow = await session.get(WorkflowRecord, completed_workflow_id)
        assert review_workflow is not None
        assert completed_workflow is not None
        review_workflow.state = "HUMAN_REVIEW_REQUIRED"
        completed_workflow.state = "COMPLETED"
        await session.commit()

    response = await client.get("/api/v1/reviews/human-review-queue")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["workflow_id"] == review_workflow_id
    assert body["items"][0]["state"] == "HUMAN_REVIEW_REQUIRED"
    assert body["items"][0]["priority"] == "HIGH"
    assert body["items"][0]["metadata"] == {"case_reference": "MORT-REVIEW"}


async def test_get_workflow_approvals_returns_persisted_records(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    create_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "approval-query-test"},
        json={},
    )
    workflow_id = create_response.json()["workflow_id"]

    _, session_factory = app_context
    now = utc_now()
    async with session_factory() as session:
        session.add(
            ApprovalRecord(
                approval_id="00000000-0000-0000-0000-000000000301",
                workflow_id=workflow_id,
                correlation_id="approval-query-test",
                decision="APPROVED",
                decision_reason="exception_review_completed",
                comment="Operator approved the prepared exception review.",
                reviewed_by="operator-1",
                reviewed_at=now,
                approval_metadata={"review_channel": "operator_console"},
                created_at=now,
            )
        )
        await session.commit()

    response = await client.get(f"/api/v1/workflows/{workflow_id}/approvals")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_id"] == workflow_id
    assert len(body["approvals"]) == 1
    assert body["approvals"][0]["decision"] == "APPROVED"
    assert body["approvals"][0]["reviewed_by"] == "operator-1"
    assert body["approvals"][0]["metadata"] == {"review_channel": "operator_console"}


async def test_get_workflow_evaluations_returns_persisted_runs_and_results(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    create_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "evaluation-query-test"},
        json={},
    )
    workflow_id = create_response.json()["workflow_id"]

    _, session_factory = app_context
    now = utc_now()
    async with session_factory() as session:
        session.add(
            EvaluationRun(
                evaluation_run_id="00000000-0000-0000-0000-000000000501",
                workflow_id=workflow_id,
                correlation_id="evaluation-query-test",
                evaluation_scope="workflow",
                evaluation_mode="dataset_replay",
                dataset_id="mortgage-exception-local-v1",
                status="COMPLETED",
                started_at=now,
                completed_at=now,
                created_by="evaluation-service",
                run_metadata={
                    "dataset_case_id": "mortgage-exception-local-v1:approval",
                    "replay_boundary": "dataset_evaluation_only",
                },
                created_at=now,
            )
        )
        session.add(
            EvaluationResult(
                evaluation_result_id="00000000-0000-0000-0000-000000000502",
                evaluation_run_id="00000000-0000-0000-0000-000000000501",
                workflow_id=workflow_id,
                agent_execution_id=None,
                prompt_id=None,
                prompt_version=None,
                model_name=None,
                evaluator_id="dataset-replay-contract",
                evaluator_version="v1",
                score_name="dataset_case_alignment",
                score_value=1.0,
                score_status="PASS",
                severity="informational",
                rationale="Workflow evidence satisfied the selected local dataset case.",
                result_metadata={"expected_tools": ["borrower_profile_lookup", "document_fetch"]},
                created_at=now,
            )
        )
        await session.commit()

    response = await client.get(f"/api/v1/workflows/{workflow_id}/evaluations")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_id"] == workflow_id
    assert body["count"] == 1
    assert body["runs"][0]["evaluation_mode"] == "dataset_replay"
    assert body["runs"][0]["dataset_id"] == "mortgage-exception-local-v1"
    assert body["runs"][0]["metadata"]["dataset_case_id"] == "mortgage-exception-local-v1:approval"
    assert body["runs"][0]["results"][0]["evaluator_id"] == "dataset-replay-contract"
    assert body["runs"][0]["results"][0]["score_status"] == "PASS"
    assert body["runs"][0]["results"][0]["metadata"]["expected_tools"] == [
        "borrower_profile_lookup",
        "document_fetch",
    ]


async def test_get_workflow_review_context_aggregates_review_records(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    create_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "review-context-test"},
        json={},
    )
    workflow_id = create_response.json()["workflow_id"]

    _, session_factory = app_context
    now = utc_now()
    async with session_factory() as session:
        workflow = await session.get(WorkflowRecord, workflow_id)
        assert workflow is not None
        workflow.state = "HUMAN_REVIEW_REQUIRED"
        session.add(
            AgentExecutionRecord(
                agent_execution_id="00000000-0000-0000-0000-000000000401",
                workflow_id=workflow_id,
                agent_id="document_analysis_agent",
                prompt_id="document-analysis-agent",
                prompt_version="1",
                model_name="deterministic-langgraph-local-v1",
                status="COMPLETED",
                validation_status="VALIDATED",
                confidence_score=0.87,
                requires_human_review=True,
                input_metadata={"workflow_id": workflow_id},
                output_payload={"recommended_next_state": "RISK_REVIEW_PENDING"},
                execution_metadata={"workflow_state": "DOCUMENT_ANALYSIS_PENDING"},
                error_message=None,
                correlation_id="review-context-test",
                created_by="workflow-engine",
                started_at=now,
                completed_at=now,
                created_at=now,
            )
        )
        session.add(
            ToolInvocationRecord(
                tool_invocation_id="00000000-0000-0000-0000-000000000402",
                workflow_id=workflow_id,
                correlation_id="review-context-test",
                agent_execution_id="00000000-0000-0000-0000-000000000401",
                agent_id="document_analysis_agent",
                tool_id="document_fetch",
                status="COMPLETED",
                permission_status="AUTHORIZED",
                input_validation_status="VALIDATED",
                output_validation_status="VALIDATED",
                input_metadata={"requested_document_types": ["income"]},
                output_payload={"missing_document_types": ["income"]},
                execution_metadata={"replay_safe": True},
                error_message=None,
                created_by="workflow-engine",
                started_at=now,
                completed_at=now,
                created_at=now,
            )
        )
        await session.commit()

    response = await client.get(f"/api/v1/workflows/{workflow_id}/review-context")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow"]["workflow_id"] == workflow_id
    assert body["workflow"]["state"] == "HUMAN_REVIEW_REQUIRED"
    assert len(body["timeline"]) == 1
    assert body["agent_executions"][0]["agent_id"] == "document_analysis_agent"
    assert body["tool_invocations"][0]["tool_id"] == "document_fetch"
    assert body["approvals"] == []


async def test_create_workflow_approval_dispatches_temporal_decision_workflow(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "approval-create-test"},
        json={},
    )
    workflow_id = create_response.json()["workflow_id"]

    _, session_factory = app_context
    async with session_factory() as session:
        workflow = await session.get(WorkflowRecord, workflow_id)
        assert workflow is not None
        workflow.state = "HUMAN_REVIEW_REQUIRED"
        await session.commit()

    async def fake_apply_human_review_decision(
        self: TemporalWorkflowStarter,
        payload: dict,
    ) -> dict:
        now = utc_now()
        async with session_factory() as session:
            workflow = await session.get(WorkflowRecord, payload["workflow_id"])
            assert workflow is not None
            workflow.state = "COMPLETED"
            workflow.completed_at = now
            session.add(
                ApprovalRecord(
                    approval_id=payload["approval_id"],
                    workflow_id=payload["workflow_id"],
                    correlation_id=payload["correlation_id"],
                    decision=payload["decision"],
                    decision_reason=payload["decision_reason"],
                    comment=payload["comment"],
                    reviewed_by=payload["reviewed_by"],
                    reviewed_at=now,
                    approval_metadata=payload["approval_metadata"],
                    created_at=now,
                )
            )
            await session.commit()
        return {
            "workflow_id": payload["workflow_id"],
            "approval_id": payload["approval_id"],
            "decision": payload["decision"],
            "state": "COMPLETED",
            "idempotent": False,
        }

    monkeypatch.setattr(
        TemporalWorkflowStarter,
        "apply_human_review_decision",
        fake_apply_human_review_decision,
    )

    response = await client.post(
        f"/api/v1/workflows/{workflow_id}/approvals",
        headers={"X-Actor-ID": "operator-1"},
        json={
            "decision": "APPROVED",
            "decision_reason": "exception_review_completed",
            "comment": "Reviewed prepared case context and approved completion.",
            "metadata": {"review_channel": "operator_console"},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["workflow"]["state"] == "COMPLETED"
    assert body["approval"]["decision"] == "APPROVED"
    assert body["approval"]["reviewed_by"] == "operator-1"
    assert body["approval"]["metadata"]["review_channel"] == "operator_console"
    assert body["decision_result"]["state"] == "COMPLETED"


async def test_create_workflow_approval_requires_actor_id(client: AsyncClient) -> None:
    create_response = await client.post("/api/v1/workflows", json={})
    workflow_id = create_response.json()["workflow_id"]

    response = await client.post(
        f"/api/v1/workflows/{workflow_id}/approvals",
        json={
            "decision": "APPROVED",
            "decision_reason": "exception_review_completed",
            "comment": "Reviewed prepared case context.",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "actor_required"


async def test_create_workflow_approval_rejects_non_reviewable_workflow(client: AsyncClient) -> None:
    create_response = await client.post("/api/v1/workflows", json={})
    workflow_id = create_response.json()["workflow_id"]

    response = await client.post(
        f"/api/v1/workflows/{workflow_id}/approvals",
        headers={"X-Actor-ID": "operator-1"},
        json={
            "decision": "REJECTED",
            "decision_reason": "exception_review_incomplete",
            "comment": "Required support is incomplete.",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"] == "workflow_not_reviewable"
