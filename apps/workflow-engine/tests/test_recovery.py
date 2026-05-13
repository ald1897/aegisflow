from collections.abc import AsyncIterator
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from temporalio.exceptions import ApplicationError

from aegisflow_workflow_engine.activities import recovery as recovery_activity
from aegisflow_workflow_engine.persistence.models import (
    Base,
    WorkflowEventOutbox,
    WorkflowRecoveryAction,
    WorkflowRecord,
    WorkflowStateTransition,
    WorkflowTimelineEntry,
)


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield factory

    await engine.dispose()


async def test_reconcile_workflow_projection_updates_state_timeline_and_outbox(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(recovery_activity, "SessionLocal", session_factory)
    workflow_id = "00000000-0000-0000-0000-000000002600"
    recovery_action_id = "00000000-0000-0000-0000-000000002700"
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        _add_workflow(session, workflow_id=workflow_id, state="NEW", now=now)
        session.add(
            WorkflowStateTransition(
                transition_id="00000000-0000-0000-0000-000000002601",
                workflow_id=workflow_id,
                prior_state="NEW",
                new_state="INTAKE_IN_PROGRESS",
                transition_reason="engine_transition_completed_projection_stale",
                correlation_id="workflow-recovery-engine-test",
                created_by="workflow-engine",
                created_at=now,
            )
        )
        session.add(
            WorkflowRecoveryAction(
                recovery_action_id=recovery_action_id,
                workflow_id=workflow_id,
                correlation_id="workflow-recovery-engine-test",
                action_type="reconcile_workflow_projection",
                target_resource_type="workflow_record",
                target_resource_id=workflow_id,
                status="REQUESTED",
                requested_by="operator-1",
                reason="Projection is stale after local worker interruption.",
                started_at=now,
                completed_at=None,
                result_metadata={"dry_run_allowed": True},
                created_at=now,
            )
        )
        await session.commit()

    result = await recovery_activity.reconcile_workflow_projection(
        {
            "workflow_id": workflow_id,
            "recovery_action_id": recovery_action_id,
            "correlation_id": "workflow-recovery-engine-test",
            "action_type": "reconcile_workflow_projection",
            "requested_by": "operator-1",
            "reason": "Projection is stale after local worker interruption.",
        }
    )

    async with session_factory() as session:
        workflow = await session.get(WorkflowRecord, workflow_id)
        recovery_action = await session.get(WorkflowRecoveryAction, recovery_action_id)
        timeline_entry = (await session.execute(select(WorkflowTimelineEntry))).scalar_one()
        outbox_event = (await session.execute(select(WorkflowEventOutbox))).scalar_one()

    assert result["engine_owned_mutation"] is True
    assert workflow is not None
    assert workflow.state == "INTAKE_IN_PROGRESS"
    assert recovery_action is not None
    assert recovery_action.status == "COMPLETED"
    assert recovery_action.completed_at is not None
    assert recovery_action.result_metadata["reconciled_state"] == "INTAKE_IN_PROGRESS"
    assert recovery_action.result_metadata["sensitive_payloads_persisted"] is False
    assert timeline_entry.entry_type == "RECOVERY_ACTION_RECORDED"
    assert timeline_entry.state == "INTAKE_IN_PROGRESS"
    assert timeline_entry.entry_metadata["reason_present"] is True
    assert outbox_event.event_type == "recovery.action_completed"
    assert outbox_event.publish_status == "PENDING"
    assert outbox_event.payload["reconciled_state"] == "INTAKE_IN_PROGRESS"


async def test_reconcile_workflow_projection_dry_run_does_not_mutate(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(recovery_activity, "SessionLocal", session_factory)
    workflow_id = "00000000-0000-0000-0000-000000002601"
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        _add_workflow(session, workflow_id=workflow_id, state="NEW", now=now)
        session.add(
            WorkflowStateTransition(
                transition_id="00000000-0000-0000-0000-000000002602",
                workflow_id=workflow_id,
                prior_state="NEW",
                new_state="INTAKE_IN_PROGRESS",
                transition_reason="engine_transition_completed_projection_stale",
                correlation_id="workflow-recovery-dry-run-test",
                created_by="workflow-engine",
                created_at=now,
            )
        )
        await session.commit()

    result = await recovery_activity.reconcile_workflow_projection(
        {
            "workflow_id": workflow_id,
            "recovery_action_id": "00000000-0000-0000-0000-000000002701",
            "correlation_id": "workflow-recovery-dry-run-test",
            "action_type": "reconcile_workflow_projection",
            "requested_by": "operator-1",
            "reason": "Check projection recovery.",
            "dry_run": True,
        }
    )

    async with session_factory() as session:
        workflow = await session.get(WorkflowRecord, workflow_id)
        recovery_actions = (await session.execute(select(WorkflowRecoveryAction))).scalars().all()
        timeline_entries = (await session.execute(select(WorkflowTimelineEntry))).scalars().all()
        outbox_events = (await session.execute(select(WorkflowEventOutbox))).scalars().all()

    assert result["dry_run"] is True
    assert result["allowed"] is True
    assert result["engine_owned_mutation"] is False
    assert workflow is not None
    assert workflow.state == "NEW"
    assert recovery_actions == []
    assert timeline_entries == []
    assert outbox_events == []


async def test_reconcile_workflow_projection_rejects_unsupported_or_incomplete_commands(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(recovery_activity, "SessionLocal", session_factory)
    workflow_id = "00000000-0000-0000-0000-000000002602"
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        _add_workflow(session, workflow_id=workflow_id, state="NEW", now=now)
        await session.commit()

    with pytest.raises(ApplicationError, match="Unsupported workflow recovery action"):
        await recovery_activity.reconcile_workflow_projection(
            {
                "workflow_id": workflow_id,
                "recovery_action_id": "00000000-0000-0000-0000-000000002702",
                "correlation_id": "workflow-recovery-reject-test",
                "action_type": "retry_outbox_event",
                "requested_by": "operator-1",
                "reason": "Unsupported workflow recovery.",
            }
        )

    with pytest.raises(ApplicationError, match="requires requested_by"):
        await recovery_activity.reconcile_workflow_projection(
            {
                "workflow_id": workflow_id,
                "recovery_action_id": "00000000-0000-0000-0000-000000002703",
                "correlation_id": "workflow-recovery-reject-test",
                "action_type": "reconcile_workflow_projection",
                "requested_by": "",
                "reason": "Missing actor.",
            }
        )


def _add_workflow(
    session: AsyncSession,
    *,
    workflow_id: str,
    state: str,
    now: datetime,
) -> None:
    session.add(
        WorkflowRecord(
            workflow_id=workflow_id,
            workflow_type="MORTGAGE_EXCEPTION_REVIEW",
            state=state,
            priority="NORMAL",
            correlation_id="workflow-recovery-engine-test",
            created_by="tester",
            workflow_metadata={},
            temporal_workflow_id=None,
            temporal_run_id=None,
            started_at=now,
            completed_at=None,
            failed_at=None,
            created_at=now,
            updated_at=now,
        )
    )
