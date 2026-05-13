from collections.abc import AsyncIterator
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from aegisflow_gateway.config import Settings, get_settings
from aegisflow_gateway.domain.workflows import (
    RecoveryActionStatus,
    RecoveryActionType,
    ReplayMode,
    ReplayRunStatus,
    ReplayStepStatus,
)
from aegisflow_gateway.main import create_app
from aegisflow_gateway.persistence.database import get_session
from aegisflow_gateway.persistence.models import (
    AgentExecutionRecord,
    ApprovalRecord,
    Base,
    EvaluationResult,
    EvaluationRun,
    ToolInvocationRecord,
    WorkflowRecoveryAction,
    WorkflowEventOutbox,
    WorkflowRecord,
    WorkflowReplayRun,
    WorkflowReplayStep,
    WorkflowStateTransition,
    WorkflowTimelineEntry,
)
from aegisflow_gateway.persistence.models import utc_now
from aegisflow_gateway.services.temporal import TemporalWorkflowStarter
from aegisflow_gateway.services.workflows import WorkflowService


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

    def override_get_settings() -> Settings:
        settings = Settings()
        settings.enable_event_publishing = False
        settings.enable_temporal_start = False
        settings.enable_telemetry = False
        return settings

    app.dependency_overrides[get_settings] = override_get_settings

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


async def test_replay_run_and_steps_can_be_persisted_and_listed(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    create_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "replay-persistence-test"},
        json={},
    )
    workflow_id = UUID(create_response.json()["workflow_id"])

    _, session_factory = app_context
    async with session_factory() as session:
        workflow = await session.get(WorkflowRecord, str(workflow_id))
        assert workflow is not None
        workflow.temporal_workflow_id = f"mortgage-exception-review-{workflow_id}"
        workflow.temporal_run_id = "temporal-run-1"
        await session.commit()

    async with session_factory() as session:
        service = WorkflowService(session)
        replay_run = await service.create_replay_run(
            workflow_id,
            replay_mode=ReplayMode.history_reconstruction,
            requested_by="operator-1",
            metadata={"boundary": "side_effect_free"},
        )
        replay_step = await service.create_replay_step(
            UUID(replay_run.replay_run_id),
            sequence_number=1,
            artifact_type="workflow_state_transition",
            artifact_id="transition-1",
            expected_state="NEW",
            observed_state="NEW",
            status=ReplayStepStatus.pass_,
            message="Initial workflow state was reconstructed.",
            metadata={"sensitive_payloads_persisted": False},
        )
        runs = await service.list_replay_runs(workflow_id)
        steps = await service.list_replay_steps(UUID(replay_run.replay_run_id))

    assert len(runs) == 1
    assert runs[0].replay_run_id == replay_run.replay_run_id
    assert runs[0].correlation_id == "replay-persistence-test"
    assert runs[0].replay_mode == ReplayMode.history_reconstruction.value
    assert runs[0].status == ReplayRunStatus.requested.value
    assert runs[0].source_temporal_workflow_id == f"mortgage-exception-review-{workflow_id}"
    assert runs[0].source_temporal_run_id == "temporal-run-1"
    assert runs[0].requested_by == "operator-1"
    assert runs[0].replay_metadata == {"boundary": "side_effect_free"}
    assert len(steps) == 1
    assert steps[0].replay_step_id == replay_step.replay_step_id
    assert steps[0].sequence_number == 1
    assert steps[0].artifact_type == "workflow_state_transition"
    assert steps[0].status == ReplayStepStatus.pass_.value
    assert steps[0].step_metadata == {"sensitive_payloads_persisted": False}

    async with session_factory() as session:
        replay_run_count = len((await session.execute(select(WorkflowReplayRun))).scalars().all())
        replay_step_count = len((await session.execute(select(WorkflowReplayStep))).scalars().all())

    assert replay_run_count == 1
    assert replay_step_count == 1


async def test_recovery_action_can_be_persisted_and_listed(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    create_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "recovery-persistence-test"},
        json={},
    )
    workflow_id = UUID(create_response.json()["workflow_id"])

    _, session_factory = app_context
    async with session_factory() as session:
        service = WorkflowService(session)
        recovery_action = await service.create_recovery_action(
            workflow_id,
            action_type=RecoveryActionType.retry_outbox_event,
            target_resource_type="workflow_event_outbox",
            target_resource_id=f"{workflow_id}:workflow.created",
            requested_by="operator-1",
            reason="Retry local event publication after transient publisher failure.",
            metadata={"raw_payload_persisted": False},
        )
        actions = await service.list_recovery_actions(workflow_id)
        retrieved_action = await service.get_recovery_action(UUID(recovery_action.recovery_action_id))

    assert len(actions) == 1
    assert actions[0].recovery_action_id == recovery_action.recovery_action_id
    assert retrieved_action.recovery_action_id == recovery_action.recovery_action_id
    assert retrieved_action.correlation_id == "recovery-persistence-test"
    assert retrieved_action.action_type == RecoveryActionType.retry_outbox_event.value
    assert retrieved_action.target_resource_type == "workflow_event_outbox"
    assert retrieved_action.status == RecoveryActionStatus.requested.value
    assert retrieved_action.requested_by == "operator-1"
    assert retrieved_action.reason == "Retry local event publication after transient publisher failure."
    assert retrieved_action.result_metadata == {"raw_payload_persisted": False}

    async with session_factory() as session:
        recovery_action_count = len((await session.execute(select(WorkflowRecoveryAction))).scalars().all())

    assert recovery_action_count == 1


async def _seed_workflow_evidence(
    session: AsyncSession,
    workflow_id: str,
    *,
    correlation_id: str,
    final_state: str,
    decision: str | None = None,
    include_evaluation: bool = False,
) -> None:
    now = utc_now()
    workflow = await session.get(WorkflowRecord, workflow_id)
    assert workflow is not None
    terminal_decision = decision if final_state == "COMPLETED" else None
    workflow.state = final_state
    workflow.temporal_workflow_id = f"mortgage-exception-review-{workflow_id}"
    workflow.temporal_run_id = "temporal-run-1"
    if final_state == "COMPLETED":
        assert terminal_decision is not None
        workflow.completed_at = now + timedelta(minutes=7)

    created_event = await session.get(WorkflowEventOutbox, f"{workflow_id}:workflow.created")
    assert created_event is not None
    created_event.publish_status = "PUBLISHED"
    created_event.published_at = now

    session.add_all(
        [
            WorkflowStateTransition(
                transition_id="00000000-0000-0000-0000-000000000601",
                workflow_id=workflow_id,
                prior_state="NEW",
                new_state="INTAKE_IN_PROGRESS",
                transition_reason="test_intake_started",
                correlation_id=correlation_id,
                created_by="workflow-engine",
                created_at=now + timedelta(minutes=1),
            ),
            WorkflowStateTransition(
                transition_id="00000000-0000-0000-0000-000000000602",
                workflow_id=workflow_id,
                prior_state="INTAKE_IN_PROGRESS",
                new_state="DOCUMENT_ANALYSIS_PENDING",
                transition_reason="test_intake_completed",
                correlation_id=correlation_id,
                created_by="workflow-engine",
                created_at=now + timedelta(minutes=2),
            ),
            WorkflowStateTransition(
                transition_id="00000000-0000-0000-0000-000000000603",
                workflow_id=workflow_id,
                prior_state="DOCUMENT_ANALYSIS_PENDING",
                new_state="RISK_REVIEW_PENDING",
                transition_reason="test_risk_review_started",
                correlation_id=correlation_id,
                created_by="workflow-engine",
                created_at=now + timedelta(minutes=3),
            ),
            WorkflowStateTransition(
                transition_id="00000000-0000-0000-0000-000000000604",
                workflow_id=workflow_id,
                prior_state="RISK_REVIEW_PENDING",
                new_state="HUMAN_REVIEW_REQUIRED",
                transition_reason="test_review_required",
                correlation_id=correlation_id,
                created_by="workflow-engine",
                created_at=now + timedelta(minutes=4),
            ),
            WorkflowTimelineEntry(
                timeline_entry_id="00000000-0000-0000-0000-000000000621",
                workflow_id=workflow_id,
                entry_type="STATE_TRANSITION",
                message="Workflow advanced through local mortgage review states.",
                state="HUMAN_REVIEW_REQUIRED",
                correlation_id=correlation_id,
                created_by="workflow-engine",
                entry_metadata={"new_state": "HUMAN_REVIEW_REQUIRED"},
                created_at=now + timedelta(minutes=4),
            ),
            WorkflowTimelineEntry(
                timeline_entry_id="00000000-0000-0000-0000-000000000622",
                workflow_id=workflow_id,
                entry_type="AGENT_EXECUTION_COMPLETED",
                message="Intake agent completed.",
                state="INTAKE_IN_PROGRESS",
                correlation_id=correlation_id,
                created_by="workflow-engine",
                entry_metadata={"agent_id": "intake_agent"},
                created_at=now + timedelta(minutes=2),
            ),
            WorkflowTimelineEntry(
                timeline_entry_id="00000000-0000-0000-0000-000000000623",
                workflow_id=workflow_id,
                entry_type="TOOL_INVOCATION_COMPLETED",
                message="Document fetch completed.",
                state="DOCUMENT_ANALYSIS_PENDING",
                correlation_id=correlation_id,
                created_by="workflow-engine",
                entry_metadata={"tool_id": "document_fetch", "replay_safe": True},
                created_at=now + timedelta(minutes=3),
            ),
            AgentExecutionRecord(
                agent_execution_id="00000000-0000-0000-0000-000000000611",
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
                correlation_id=correlation_id,
                created_by="workflow-engine",
                started_at=now + timedelta(minutes=1),
                completed_at=now + timedelta(minutes=2),
                created_at=now + timedelta(minutes=2),
            ),
            AgentExecutionRecord(
                agent_execution_id="00000000-0000-0000-0000-000000000612",
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
                correlation_id=correlation_id,
                created_by="workflow-engine",
                started_at=now + timedelta(minutes=2),
                completed_at=now + timedelta(minutes=3),
                created_at=now + timedelta(minutes=3),
            ),
            ToolInvocationRecord(
                tool_invocation_id="00000000-0000-0000-0000-000000000613",
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                agent_execution_id="00000000-0000-0000-0000-000000000611",
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
                started_at=now + timedelta(minutes=1),
                completed_at=now + timedelta(minutes=2),
                created_at=now + timedelta(minutes=2),
            ),
            ToolInvocationRecord(
                tool_invocation_id="00000000-0000-0000-0000-000000000614",
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                agent_execution_id="00000000-0000-0000-0000-000000000612",
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
                started_at=now + timedelta(minutes=2),
                completed_at=now + timedelta(minutes=3),
                created_at=now + timedelta(minutes=3),
            ),
            WorkflowEventOutbox(
                event_id=f"{workflow_id}:workflow.state_changed:HUMAN_REVIEW_REQUIRED",
                event_type="workflow.state_changed",
                event_version="1",
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                payload={"workflow_id": workflow_id, "new_state": "HUMAN_REVIEW_REQUIRED"},
                publish_status="PUBLISHED",
                retry_count=0,
                last_error=None,
                created_at=now + timedelta(minutes=4),
                published_at=now + timedelta(minutes=4),
            ),
            WorkflowEventOutbox(
                event_id=f"{workflow_id}:agent.execution_completed:document_analysis_agent",
                event_type="agent.execution_completed",
                event_version="1",
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                payload={"workflow_id": workflow_id, "agent_id": "document_analysis_agent"},
                publish_status="PUBLISHED",
                retry_count=0,
                last_error=None,
                created_at=now + timedelta(minutes=3),
                published_at=now + timedelta(minutes=3),
            ),
            WorkflowEventOutbox(
                event_id=f"{workflow_id}:tool.invocation_completed:document_fetch",
                event_type="tool.invocation_completed",
                event_version="1",
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                payload={"workflow_id": workflow_id, "tool_id": "document_fetch"},
                publish_status="PUBLISHED",
                retry_count=0,
                last_error=None,
                created_at=now + timedelta(minutes=3),
                published_at=now + timedelta(minutes=3),
            ),
        ]
    )

    if decision is not None:
        session.add_all(
            [
                WorkflowStateTransition(
                    transition_id="00000000-0000-0000-0000-000000000605",
                    workflow_id=workflow_id,
                    prior_state="HUMAN_REVIEW_REQUIRED",
                    new_state=decision,
                    transition_reason="test_human_review_decision",
                    correlation_id=correlation_id,
                    created_by="workflow-engine",
                    created_at=now + timedelta(minutes=6),
                ),
                WorkflowStateTransition(
                    transition_id="00000000-0000-0000-0000-000000000606",
                    workflow_id=workflow_id,
                    prior_state=decision,
                    new_state="COMPLETED",
                    transition_reason="test_workflow_completed",
                    correlation_id=correlation_id,
                    created_by="workflow-engine",
                    created_at=now + timedelta(minutes=7),
                ),
                WorkflowTimelineEntry(
                    timeline_entry_id="00000000-0000-0000-0000-000000000624",
                    workflow_id=workflow_id,
                    entry_type="APPROVAL_DECISION_RECORDED",
                    message="Human review decision recorded.",
                    state=decision,
                    correlation_id=correlation_id,
                    created_by="workflow-engine",
                    entry_metadata={"decision": decision},
                    created_at=now + timedelta(minutes=6),
                ),
                ApprovalRecord(
                    approval_id="00000000-0000-0000-0000-000000000609",
                    workflow_id=workflow_id,
                    correlation_id=correlation_id,
                    decision=decision,
                    decision_reason="exception_review_completed",
                    comment=f"Operator {decision.lower()} the prepared exception review.",
                    reviewed_by="operator-1",
                    reviewed_at=now + timedelta(minutes=6),
                    approval_metadata={"review_channel": "operator_console"},
                    created_at=now + timedelta(minutes=6),
                ),
                WorkflowEventOutbox(
                    event_id=f"{workflow_id}:approval.decision_recorded:{decision}",
                    event_type="approval.decision_recorded",
                    event_version="1",
                    workflow_id=workflow_id,
                    correlation_id=correlation_id,
                    payload={"workflow_id": workflow_id, "decision": decision},
                    publish_status="PUBLISHED",
                    retry_count=0,
                    last_error=None,
                    created_at=now + timedelta(minutes=6),
                    published_at=now + timedelta(minutes=6),
                ),
                WorkflowEventOutbox(
                    event_id=f"{workflow_id}:workflow.{decision.lower()}:{decision}",
                    event_type=f"workflow.{decision.lower()}",
                    event_version="1",
                    workflow_id=workflow_id,
                    correlation_id=correlation_id,
                    payload={"workflow_id": workflow_id, "new_state": decision},
                    publish_status="PUBLISHED",
                    retry_count=0,
                    last_error=None,
                    created_at=now + timedelta(minutes=6),
                    published_at=now + timedelta(minutes=6),
                ),
                WorkflowEventOutbox(
                    event_id=f"{workflow_id}:workflow.completed:COMPLETED",
                    event_type="workflow.completed",
                    event_version="1",
                    workflow_id=workflow_id,
                    correlation_id=correlation_id,
                    payload={"workflow_id": workflow_id, "new_state": "COMPLETED"},
                    publish_status="PUBLISHED",
                    retry_count=0,
                    last_error=None,
                    created_at=now + timedelta(minutes=7),
                    published_at=now + timedelta(minutes=7),
                ),
            ]
        )

    if include_evaluation:
        session.add(
            EvaluationRun(
                evaluation_run_id="00000000-0000-0000-0000-000000000610",
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                evaluation_scope="workflow",
                evaluation_mode="dataset_replay",
                dataset_id="mortgage-exception-local-v1",
                status="COMPLETED",
                started_at=now + timedelta(minutes=8),
                completed_at=now + timedelta(minutes=8),
                created_by="evaluation-service",
                run_metadata={"dataset_case_id": f"mortgage-exception-local-v1:{decision.lower()}"},
                created_at=now + timedelta(minutes=8),
            )
        )
        session.add(
            EvaluationResult(
                evaluation_result_id="00000000-0000-0000-0000-000000000611",
                evaluation_run_id="00000000-0000-0000-0000-000000000610",
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
                result_metadata={"expected_decision": decision},
                created_at=now + timedelta(minutes=8),
            )
        )

    await session.commit()


async def test_reconstruct_workflow_evidence_for_completed_approval_workflow(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    create_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "approval-evidence-test"},
        json={},
    )
    workflow_id = create_response.json()["workflow_id"]

    _, session_factory = app_context
    async with session_factory() as session:
        await _seed_workflow_evidence(
            session,
            workflow_id,
            correlation_id="approval-evidence-test",
            final_state="COMPLETED",
            decision="APPROVED",
            include_evaluation=True,
        )

    async with session_factory() as session:
        snapshot = await WorkflowService(session).reconstruct_workflow_evidence(UUID(workflow_id))

    assert snapshot.workflow_id == workflow_id
    assert snapshot.workflow_state == "COMPLETED"
    assert snapshot.artifact_counts["workflow_record"] == 1
    assert snapshot.artifact_counts["agent_execution_record"] == 2
    assert snapshot.artifact_counts["tool_invocation_record"] == 2
    assert snapshot.artifact_counts["approval_record"] == 1
    assert snapshot.artifact_counts["evaluation_run"] == 1
    assert snapshot.artifact_counts["evaluation_result"] == 1
    assert [diagnostic.code for diagnostic in snapshot.diagnostics] == ["evidence_snapshot_complete"]
    assert {artifact.correlation_id for artifact in snapshot.artifacts} == {"approval-evidence-test"}

    sort_keys = [(artifact.occurred_at, artifact.artifact_type, artifact.artifact_id) for artifact in snapshot.artifacts]
    assert sort_keys == sorted(sort_keys)
    approval_artifact = snapshot.artifacts_by_type("approval_record")[0]
    assert approval_artifact.status == "APPROVED"
    assert approval_artifact.metadata["comment_present"] is True
    assert "Operator approved the prepared exception review." not in str(snapshot)


async def test_reconstruct_workflow_evidence_for_completed_rejection_workflow(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    create_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "rejection-evidence-test"},
        json={},
    )
    workflow_id = create_response.json()["workflow_id"]

    _, session_factory = app_context
    async with session_factory() as session:
        await _seed_workflow_evidence(
            session,
            workflow_id,
            correlation_id="rejection-evidence-test",
            final_state="COMPLETED",
            decision="REJECTED",
            include_evaluation=True,
        )

    async with session_factory() as session:
        snapshot = await WorkflowService(session).reconstruct_workflow_evidence(UUID(workflow_id))

    assert snapshot.workflow_state == "COMPLETED"
    assert snapshot.artifact_counts["approval_record"] == 1
    assert snapshot.artifacts_by_type("approval_record")[0].status == "REJECTED"
    assert snapshot.artifacts_by_type("evaluation_result")[0].metadata["score_name"] == "dataset_case_alignment"
    assert [diagnostic.status for diagnostic in snapshot.diagnostics] == ["PASS"]


async def test_reconstruct_workflow_evidence_flags_human_review_in_progress(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    create_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "review-pending-evidence-test"},
        json={},
    )
    workflow_id = create_response.json()["workflow_id"]

    _, session_factory = app_context
    async with session_factory() as session:
        await _seed_workflow_evidence(
            session,
            workflow_id,
            correlation_id="review-pending-evidence-test",
            final_state="HUMAN_REVIEW_REQUIRED",
            decision=None,
            include_evaluation=False,
        )

    async with session_factory() as session:
        before_counts = {
            "workflows": len((await session.execute(select(WorkflowRecord))).scalars().all()),
            "approvals": len((await session.execute(select(ApprovalRecord))).scalars().all()),
            "replay_runs": len((await session.execute(select(WorkflowReplayRun))).scalars().all()),
        }
        snapshot = await WorkflowService(session).reconstruct_workflow_evidence(UUID(workflow_id))
        after_counts = {
            "workflows": len((await session.execute(select(WorkflowRecord))).scalars().all()),
            "approvals": len((await session.execute(select(ApprovalRecord))).scalars().all()),
            "replay_runs": len((await session.execute(select(WorkflowReplayRun))).scalars().all()),
        }

    assert before_counts == after_counts
    assert snapshot.workflow_state == "HUMAN_REVIEW_REQUIRED"
    assert snapshot.artifact_counts.get("approval_record") is None
    diagnostics = {diagnostic.code: diagnostic for diagnostic in snapshot.diagnostics}
    assert diagnostics["human_review_pending"].status == "WARN"
    assert diagnostics["human_review_pending"].artifact_type == "approval_record"


async def test_validate_deterministic_replay_passes_completed_approval_workflow(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    create_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "replay-validation-pass-test"},
        json={},
    )
    workflow_id = create_response.json()["workflow_id"]

    _, session_factory = app_context
    async with session_factory() as session:
        await _seed_workflow_evidence(
            session,
            workflow_id,
            correlation_id="replay-validation-pass-test",
            final_state="COMPLETED",
            decision="APPROVED",
            include_evaluation=True,
        )

    async with session_factory() as session:
        before_replay_runs = len((await session.execute(select(WorkflowReplayRun))).scalars().all())
        result = await WorkflowService(session).validate_deterministic_replay(UUID(workflow_id))
        after_replay_runs = len((await session.execute(select(WorkflowReplayRun))).scalars().all())

    assert before_replay_runs == after_replay_runs == 0
    assert result.status == ReplayStepStatus.pass_
    assert result.step_counts == {"PASS": 7}
    assert [step.sequence_number for step in result.steps] == [1, 2, 3, 4, 5, 6, 7]
    assert result.steps[0].metadata["expected_states"] == [
        "NEW",
        "INTAKE_IN_PROGRESS",
        "DOCUMENT_ANALYSIS_PENDING",
        "RISK_REVIEW_PENDING",
        "HUMAN_REVIEW_REQUIRED",
        "APPROVED",
        "COMPLETED",
    ]
    replay_step_kwargs = result.steps[0].to_replay_step_kwargs()
    assert replay_step_kwargs["status"] == ReplayStepStatus.pass_
    assert replay_step_kwargs["metadata"]["sensitive_payloads_persisted"] is False


async def test_validate_deterministic_replay_warns_for_human_review_in_progress(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    create_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "replay-validation-warn-test"},
        json={},
    )
    workflow_id = create_response.json()["workflow_id"]

    _, session_factory = app_context
    async with session_factory() as session:
        await _seed_workflow_evidence(
            session,
            workflow_id,
            correlation_id="replay-validation-warn-test",
            final_state="HUMAN_REVIEW_REQUIRED",
            decision=None,
            include_evaluation=False,
        )

    async with session_factory() as session:
        result = await WorkflowService(session).validate_deterministic_replay(UUID(workflow_id))

    assert result.status == ReplayStepStatus.warn
    steps_by_type = {step.artifact_type: step for step in result.steps}
    assert steps_by_type["approval_record"].status == ReplayStepStatus.warn
    assert steps_by_type["approval_record"].message == (
        "Workflow is waiting for human review and has no terminal approval record yet."
    )
    assert steps_by_type["evaluation_run"].status == ReplayStepStatus.skipped


async def test_validate_deterministic_replay_fails_invalid_state_sequence(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    create_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "replay-validation-fail-test"},
        json={},
    )
    workflow_id = create_response.json()["workflow_id"]

    _, session_factory = app_context
    async with session_factory() as session:
        await _seed_workflow_evidence(
            session,
            workflow_id,
            correlation_id="replay-validation-fail-test",
            final_state="COMPLETED",
            decision="REJECTED",
            include_evaluation=True,
        )

    async with session_factory() as session:
        transition = (
            await session.execute(
                select(WorkflowStateTransition).where(
                    WorkflowStateTransition.transition_reason == "test_risk_review_started"
                )
            )
        ).scalar_one()
        await session.delete(transition)
        await session.commit()

    async with session_factory() as session:
        result = await WorkflowService(session).validate_deterministic_replay(UUID(workflow_id))

    state_step = result.steps[0]
    assert result.status == ReplayStepStatus.fail
    assert state_step.status == ReplayStepStatus.fail
    assert state_step.metadata["expected_states"] == [
        "NEW",
        "INTAKE_IN_PROGRESS",
        "DOCUMENT_ANALYSIS_PENDING",
        "RISK_REVIEW_PENDING",
        "HUMAN_REVIEW_REQUIRED",
        "REJECTED",
        "COMPLETED",
    ]
    assert state_step.metadata["observed_states"] == [
        "NEW",
        "INTAKE_IN_PROGRESS",
        "DOCUMENT_ANALYSIS_PENDING",
        "HUMAN_REVIEW_REQUIRED",
        "REJECTED",
        "COMPLETED",
    ]


async def test_create_history_reconstruction_replay_run_persists_bounded_steps(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    create_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "history-replay-orchestration-test"},
        json={},
    )
    workflow_id = UUID(create_response.json()["workflow_id"])

    _, session_factory = app_context
    async with session_factory() as session:
        await _seed_workflow_evidence(
            session,
            str(workflow_id),
            correlation_id="history-replay-orchestration-test",
            final_state="COMPLETED",
            decision="APPROVED",
            include_evaluation=True,
        )

    async with session_factory() as session:
        before_counts = {
            "transitions": len((await session.execute(select(WorkflowStateTransition))).scalars().all()),
            "approvals": len((await session.execute(select(ApprovalRecord))).scalars().all()),
            "outbox_events": len((await session.execute(select(WorkflowEventOutbox))).scalars().all()),
        }
        service = WorkflowService(session)
        replay_run = await service.create_orchestrated_replay_run(
            workflow_id,
            replay_mode=ReplayMode.history_reconstruction,
            requested_by="operator-1",
            metadata={"operator_note_present": True},
        )
        steps = await service.list_replay_steps(UUID(replay_run.replay_run_id))
        runs = await service.list_replay_runs(workflow_id)
        after_counts = {
            "transitions": len((await session.execute(select(WorkflowStateTransition))).scalars().all()),
            "approvals": len((await session.execute(select(ApprovalRecord))).scalars().all()),
            "outbox_events": len((await session.execute(select(WorkflowEventOutbox))).scalars().all()),
        }

    assert before_counts == after_counts
    assert len(runs) == 1
    assert replay_run.status == ReplayRunStatus.completed.value
    assert replay_run.completed_at is not None
    assert replay_run.replay_metadata["boundary"] == "side_effect_free"
    assert replay_run.replay_metadata["operator_note_present"] is True
    assert replay_run.replay_metadata["step_counts"]["PASS"] == len(steps)
    assert replay_run.replay_metadata["sensitive_payloads_persisted"] is False
    assert len(steps) == sum(replay_run.replay_metadata["artifact_counts"].values()) + 1
    assert steps[-1].artifact_type == "workflow_evidence_snapshot"
    assert steps[-1].step_metadata["diagnostic_code"] == "evidence_snapshot_complete"
    assert all(step.step_metadata["sensitive_payloads_persisted"] is False for step in steps)


async def test_create_deterministic_validation_replay_run_persists_validator_steps(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    create_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "deterministic-replay-orchestration-test"},
        json={},
    )
    workflow_id = UUID(create_response.json()["workflow_id"])

    _, session_factory = app_context
    async with session_factory() as session:
        await _seed_workflow_evidence(
            session,
            str(workflow_id),
            correlation_id="deterministic-replay-orchestration-test",
            final_state="COMPLETED",
            decision="REJECTED",
            include_evaluation=True,
        )

    async with session_factory() as session:
        service = WorkflowService(session)
        replay_run = await service.create_orchestrated_replay_run(
            workflow_id,
            replay_mode=ReplayMode.deterministic_validation,
            requested_by="operator-2",
        )
        retrieved_run = await service.get_replay_run(UUID(replay_run.replay_run_id))
        workflow_runs = await service.list_replay_runs(workflow_id)
        steps = await service.list_replay_steps(UUID(replay_run.replay_run_id))

    assert retrieved_run.replay_run_id == replay_run.replay_run_id
    assert workflow_runs[0].replay_run_id == replay_run.replay_run_id
    assert replay_run.status == ReplayRunStatus.completed.value
    assert replay_run.replay_mode == ReplayMode.deterministic_validation.value
    assert replay_run.replay_metadata["step_counts"] == {"PASS": 7}
    assert len(steps) == 7
    assert [step.sequence_number for step in steps] == [1, 2, 3, 4, 5, 6, 7]
    assert {step.status for step in steps} == {ReplayStepStatus.pass_.value}
    assert steps[0].artifact_type == "workflow_state_transition"


async def test_create_orchestrated_replay_run_is_idempotent_for_explicit_replay_run_id(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    create_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "replay-idempotency-orchestration-test"},
        json={},
    )
    workflow_id = UUID(create_response.json()["workflow_id"])
    replay_run_id = uuid4()

    _, session_factory = app_context
    async with session_factory() as session:
        await _seed_workflow_evidence(
            session,
            str(workflow_id),
            correlation_id="replay-idempotency-orchestration-test",
            final_state="COMPLETED",
            decision="APPROVED",
            include_evaluation=True,
        )

    async with session_factory() as session:
        service = WorkflowService(session)
        first_run = await service.create_orchestrated_replay_run(
            workflow_id,
            replay_mode=ReplayMode.deterministic_validation,
            requested_by="operator-3",
            replay_run_id=replay_run_id,
        )
        first_steps = await service.list_replay_steps(UUID(first_run.replay_run_id))
        second_run = await service.create_orchestrated_replay_run(
            workflow_id,
            replay_mode=ReplayMode.deterministic_validation,
            requested_by="operator-3",
            replay_run_id=replay_run_id,
        )
        second_steps = await service.list_replay_steps(UUID(second_run.replay_run_id))
        replay_run_count = len((await session.execute(select(WorkflowReplayRun))).scalars().all())

    assert first_run.replay_run_id == second_run.replay_run_id == str(replay_run_id)
    assert len(first_steps) == len(second_steps) == 7
    assert replay_run_count == 1


async def test_create_replay_run_preserves_incomplete_evidence_as_warning_steps(
    client: AsyncClient,
    app_context: tuple[object, async_sessionmaker[AsyncSession]],
) -> None:
    create_response = await client.post(
        "/api/v1/workflows",
        headers={"X-Correlation-ID": "replay-incomplete-evidence-orchestration-test"},
        json={},
    )
    workflow_id = UUID(create_response.json()["workflow_id"])

    _, session_factory = app_context
    async with session_factory() as session:
        await _seed_workflow_evidence(
            session,
            str(workflow_id),
            correlation_id="replay-incomplete-evidence-orchestration-test",
            final_state="HUMAN_REVIEW_REQUIRED",
            decision=None,
            include_evaluation=False,
        )

    async with session_factory() as session:
        before_approval_count = len((await session.execute(select(ApprovalRecord))).scalars().all())
        service = WorkflowService(session)
        replay_run = await service.create_orchestrated_replay_run(
            workflow_id,
            replay_mode=ReplayMode.deterministic_validation,
            requested_by="operator-4",
        )
        steps = await service.list_replay_steps(UUID(replay_run.replay_run_id))
        after_approval_count = len((await session.execute(select(ApprovalRecord))).scalars().all())

    assert before_approval_count == after_approval_count == 0
    assert replay_run.status == ReplayRunStatus.completed.value
    assert replay_run.replay_metadata["step_counts"] == {"PASS": 5, "WARN": 1, "SKIPPED": 1}
    steps_by_type = {step.artifact_type: step for step in steps}
    assert steps_by_type["approval_record"].status == ReplayStepStatus.warn.value
    assert steps_by_type["evaluation_run"].status == ReplayStepStatus.skipped.value


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
