from collections.abc import AsyncIterator
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from temporalio.exceptions import ApplicationError

from aegisflow_workflow_engine.activities import approvals as approvals_activity
from aegisflow_workflow_engine.persistence.models import (
    ApprovalRecord,
    Base,
    WorkflowEventOutbox,
    WorkflowRecord,
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


async def test_record_approval_decision_persists_record_timeline_and_event(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_id = "00000000-0000-0000-0000-000000000400"
    approval_id = "00000000-0000-0000-0000-000000000500"
    now = datetime.now(timezone.utc)

    async def no_publish(event_id: str) -> None:
        assert event_id.endswith(":approval.decision_recorded:00000000-0000-0000-0000-000000000500")

    monkeypatch.setattr(approvals_activity, "SessionLocal", session_factory)
    monkeypatch.setattr(approvals_activity, "publish_workflow_event", no_publish)

    await _create_workflow(session_factory, workflow_id=workflow_id, now=now)

    result = await approvals_activity.record_approval_decision(
        {
            "approval_id": approval_id,
            "workflow_id": workflow_id,
            "correlation_id": "approval-record-test",
            "decision": "APPROVED",
            "decision_reason": "exception_review_completed",
            "comment": "Reviewed supporting context and approved the exception.",
            "reviewed_by": "operator-1",
            "reviewed_at": now.isoformat(),
            "approval_metadata": {"review_channel": "operator_console"},
        }
    )

    async with session_factory() as session:
        approval = (await session.execute(select(ApprovalRecord))).scalar_one()
        timeline_entry = (await session.execute(select(WorkflowTimelineEntry))).scalar_one()
        outbox_event = (await session.execute(select(WorkflowEventOutbox))).scalar_one()

    assert result["idempotent"] is False
    assert approval.approval_id == approval_id
    assert approval.decision == "APPROVED"
    assert approval.reviewed_by == "operator-1"
    assert approval.approval_metadata["review_channel"] == "operator_console"
    assert timeline_entry.entry_type == "APPROVAL_DECISION_RECORDED"
    assert timeline_entry.created_by == "operator-1"
    assert timeline_entry.entry_metadata["approval_id"] == approval_id
    assert outbox_event.event_type == "approval.decision_recorded"
    assert outbox_event.publish_status == "PENDING"
    assert outbox_event.payload["decision"] == "APPROVED"


async def test_record_approval_decision_is_idempotent(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(approvals_activity, "SessionLocal", session_factory)
    monkeypatch.setattr(approvals_activity, "publish_workflow_event", _no_publish)
    workflow_id = "00000000-0000-0000-0000-000000000401"
    approval_id = "00000000-0000-0000-0000-000000000501"
    now = datetime.now(timezone.utc)
    await _create_workflow(session_factory, workflow_id=workflow_id, now=now)

    payload = {
        "approval_id": approval_id,
        "workflow_id": workflow_id,
        "correlation_id": "approval-idempotency-test",
        "decision": "REJECTED",
        "decision_reason": "exception_review_incomplete",
        "comment": "Required review support is incomplete.",
        "reviewed_by": "operator-2",
        "reviewed_at": now.isoformat(),
        "approval_metadata": {},
    }

    first = await approvals_activity.record_approval_decision(payload)
    second = await approvals_activity.record_approval_decision(payload)

    async with session_factory() as session:
        approvals = (await session.execute(select(ApprovalRecord))).scalars().all()
        timeline_entries = (await session.execute(select(WorkflowTimelineEntry))).scalars().all()
        outbox_events = (await session.execute(select(WorkflowEventOutbox))).scalars().all()

    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert len(approvals) == 1
    assert len(timeline_entries) == 1
    assert len(outbox_events) == 1


async def test_record_approval_decision_rejects_duplicate_terminal_decision(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(approvals_activity, "SessionLocal", session_factory)
    monkeypatch.setattr(approvals_activity, "publish_workflow_event", _no_publish)
    workflow_id = "00000000-0000-0000-0000-000000000402"
    now = datetime.now(timezone.utc)
    await _create_workflow(session_factory, workflow_id=workflow_id, now=now)

    await approvals_activity.record_approval_decision(
        {
            "approval_id": "00000000-0000-0000-0000-000000000502",
            "workflow_id": workflow_id,
            "correlation_id": "approval-duplicate-test",
            "decision": "APPROVED",
            "decision_reason": "exception_review_completed",
            "comment": "Approved after review.",
            "reviewed_by": "operator-1",
            "reviewed_at": now.isoformat(),
            "approval_metadata": {},
        }
    )

    with pytest.raises(ApplicationError, match="already has an approval decision"):
        await approvals_activity.record_approval_decision(
            {
                "approval_id": "00000000-0000-0000-0000-000000000503",
                "workflow_id": workflow_id,
                "correlation_id": "approval-duplicate-test",
                "decision": "REJECTED",
                "decision_reason": "exception_review_incomplete",
                "comment": "Attempted second decision.",
                "reviewed_by": "operator-2",
                "reviewed_at": now.isoformat(),
                "approval_metadata": {},
            }
        )

    async with session_factory() as session:
        approvals = (await session.execute(select(ApprovalRecord))).scalars().all()

    assert len(approvals) == 1
    assert approvals[0].decision == "APPROVED"


async def _create_workflow(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    workflow_id: str,
    now: datetime,
) -> None:
    async with session_factory() as session:
        session.add(
            WorkflowRecord(
                workflow_id=workflow_id,
                workflow_type="MORTGAGE_EXCEPTION_REVIEW",
                state="HUMAN_REVIEW_REQUIRED",
                priority="NORMAL",
                correlation_id="approval-test",
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


async def _no_publish(event_id: str) -> None:
    del event_id
