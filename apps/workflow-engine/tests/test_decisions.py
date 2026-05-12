from collections.abc import AsyncIterator
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from temporalio.exceptions import ApplicationError

from aegisflow_workflow_engine.activities import approvals as approvals_activity
from aegisflow_workflow_engine.activities import decisions as decisions_activity
from aegisflow_workflow_engine.activities import state_transitions as state_transitions_activity
from aegisflow_workflow_engine.persistence.models import (
    ApprovalRecord,
    Base,
    WorkflowEventOutbox,
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


@pytest.fixture
def patch_activity_sessions(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(approvals_activity, "SessionLocal", session_factory)
    monkeypatch.setattr(decisions_activity, "SessionLocal", session_factory)
    monkeypatch.setattr(state_transitions_activity, "SessionLocal", session_factory)
    monkeypatch.setattr(approvals_activity, "publish_workflow_event", _no_publish)
    monkeypatch.setattr(state_transitions_activity, "publish_workflow_event", _no_publish)


async def test_apply_human_review_decision_approves_and_completes_workflow(
    session_factory: async_sessionmaker[AsyncSession],
    patch_activity_sessions: None,
) -> None:
    workflow_id = "00000000-0000-0000-0000-000000000600"
    now = datetime.now(timezone.utc)
    await _create_workflow(
        session_factory,
        workflow_id=workflow_id,
        state="HUMAN_REVIEW_REQUIRED",
        now=now,
    )

    result = await decisions_activity.apply_human_review_decision(
        _decision_payload(
            workflow_id=workflow_id,
            approval_id="00000000-0000-0000-0000-000000000700",
            decision="APPROVED",
            reviewed_at=now,
        )
    )

    async with session_factory() as session:
        workflow = await session.get(WorkflowRecord, workflow_id)
        approval = (await session.execute(select(ApprovalRecord))).scalar_one()
        transitions = (await session.execute(select(WorkflowStateTransition))).scalars().all()
        timeline_entries = (await session.execute(select(WorkflowTimelineEntry))).scalars().all()
        outbox_events = (await session.execute(select(WorkflowEventOutbox))).scalars().all()

    assert result["state"] == "COMPLETED"
    assert result["idempotent"] is False
    assert workflow is not None
    assert workflow.state == "COMPLETED"
    assert workflow.completed_at is not None
    assert approval.decision == "APPROVED"
    assert [(transition.prior_state, transition.new_state) for transition in transitions] == [
        ("HUMAN_REVIEW_REQUIRED", "APPROVED"),
        ("APPROVED", "COMPLETED"),
    ]
    assert [entry.entry_type for entry in timeline_entries].count("APPROVAL_DECISION_RECORDED") == 1
    assert {event.event_type for event in outbox_events} == {
        "approval.decision_recorded",
        "workflow.approved",
        "workflow.completed",
    }


async def test_apply_human_review_decision_rejects_and_completes_workflow(
    session_factory: async_sessionmaker[AsyncSession],
    patch_activity_sessions: None,
) -> None:
    workflow_id = "00000000-0000-0000-0000-000000000601"
    now = datetime.now(timezone.utc)
    await _create_workflow(
        session_factory,
        workflow_id=workflow_id,
        state="HUMAN_REVIEW_REQUIRED",
        now=now,
    )

    result = await decisions_activity.apply_human_review_decision(
        _decision_payload(
            workflow_id=workflow_id,
            approval_id="00000000-0000-0000-0000-000000000701",
            decision="REJECTED",
            reviewed_at=now,
        )
    )

    async with session_factory() as session:
        workflow = await session.get(WorkflowRecord, workflow_id)
        outbox_events = (await session.execute(select(WorkflowEventOutbox))).scalars().all()

    assert result["state"] == "COMPLETED"
    assert workflow is not None
    assert workflow.state == "COMPLETED"
    assert {event.event_type for event in outbox_events} == {
        "approval.decision_recorded",
        "workflow.rejected",
        "workflow.completed",
    }


async def test_apply_human_review_decision_is_idempotent_after_completion(
    session_factory: async_sessionmaker[AsyncSession],
    patch_activity_sessions: None,
) -> None:
    workflow_id = "00000000-0000-0000-0000-000000000602"
    now = datetime.now(timezone.utc)
    await _create_workflow(
        session_factory,
        workflow_id=workflow_id,
        state="HUMAN_REVIEW_REQUIRED",
        now=now,
    )
    payload = _decision_payload(
        workflow_id=workflow_id,
        approval_id="00000000-0000-0000-0000-000000000702",
        decision="APPROVED",
        reviewed_at=now,
    )

    first = await decisions_activity.apply_human_review_decision(payload)
    second = await decisions_activity.apply_human_review_decision(payload)

    async with session_factory() as session:
        approvals = (await session.execute(select(ApprovalRecord))).scalars().all()
        transitions = (await session.execute(select(WorkflowStateTransition))).scalars().all()
        outbox_events = (await session.execute(select(WorkflowEventOutbox))).scalars().all()

    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert len(approvals) == 1
    assert len(transitions) == 2
    assert len(outbox_events) == 3


async def test_apply_human_review_decision_rejects_non_reviewable_workflow(
    session_factory: async_sessionmaker[AsyncSession],
    patch_activity_sessions: None,
) -> None:
    workflow_id = "00000000-0000-0000-0000-000000000603"
    now = datetime.now(timezone.utc)
    await _create_workflow(
        session_factory,
        workflow_id=workflow_id,
        state="RISK_REVIEW_PENDING",
        now=now,
    )

    with pytest.raises(ApplicationError, match="not in a human review decision state"):
        await decisions_activity.apply_human_review_decision(
            _decision_payload(
                workflow_id=workflow_id,
                approval_id="00000000-0000-0000-0000-000000000703",
                decision="APPROVED",
                reviewed_at=now,
            )
        )

    async with session_factory() as session:
        approvals = (await session.execute(select(ApprovalRecord))).scalars().all()

    assert approvals == []


async def _create_workflow(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    workflow_id: str,
    state: str,
    now: datetime,
) -> None:
    async with session_factory() as session:
        session.add(
            WorkflowRecord(
                workflow_id=workflow_id,
                workflow_type="MORTGAGE_EXCEPTION_REVIEW",
                state=state,
                priority="NORMAL",
                correlation_id="decision-test",
                created_by="tester",
                workflow_metadata={"case_reference": "MORT-123"},
                temporal_workflow_id=None,
                temporal_run_id=None,
                started_at=now,
                completed_at=None,
                failed_at=None,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()


def _decision_payload(*, workflow_id: str, approval_id: str, decision: str, reviewed_at: datetime) -> dict:
    return {
        "approval_id": approval_id,
        "workflow_id": workflow_id,
        "correlation_id": "decision-test",
        "decision": decision,
        "decision_reason": "human_review_completed",
        "comment": "Human operator reviewed the workflow context.",
        "reviewed_by": "operator-1",
        "reviewed_at": reviewed_at.isoformat(),
        "approval_metadata": {"review_channel": "operator_console"},
    }


async def _no_publish(event_id: str) -> None:
    del event_id
