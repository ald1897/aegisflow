from collections.abc import AsyncIterator
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from aegisflow_workflow_engine.activities import tools as tools_activity
from aegisflow_workflow_engine.persistence.models import (
    Base,
    ToolInvocationRecord,
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


async def test_record_tool_invocation_persists_record_timeline_and_event(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_id = "00000000-0000-0000-0000-000000000100"
    now = datetime.now(timezone.utc)

    async def no_publish(event_id: str) -> None:
        assert event_id.endswith(":tool.invocation_completed:00000000-0000-0000-0000-000000000200")

    monkeypatch.setattr(tools_activity, "SessionLocal", session_factory)
    monkeypatch.setattr(tools_activity, "publish_workflow_event", no_publish)

    async with session_factory() as session:
        session.add(
            WorkflowRecord(
                workflow_id=workflow_id,
                workflow_type="MORTGAGE_EXCEPTION_REVIEW",
                state="INTAKE_IN_PROGRESS",
                priority="NORMAL",
                correlation_id="tool-record-test",
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

    result = await tools_activity.record_tool_invocation(
        {
            "workflow_id": workflow_id,
            "correlation_id": "tool-record-test",
            "tool_invocation_id": "00000000-0000-0000-0000-000000000200",
            "agent_execution_id": None,
            "agent_id": "intake_agent",
            "tool_id": "borrower_profile_lookup",
            "status": "COMPLETED",
            "permission_status": "AUTHORIZED",
            "input_validation_status": "VALIDATED",
            "output_validation_status": "VALIDATED",
            "input_metadata": {"case_reference_present": True},
            "output_payload": {"profile_status": "FOUND"},
            "execution_metadata": {
                "data_classification": "Confidential",
                "replay_safe": True,
            },
            "error_message": None,
        }
    )

    async with session_factory() as session:
        invocation = (await session.execute(select(ToolInvocationRecord))).scalar_one()
        timeline_entry = (await session.execute(select(WorkflowTimelineEntry))).scalar_one()
        outbox_event = (await session.execute(select(WorkflowEventOutbox))).scalar_one()

    assert result["idempotent"] is False
    assert invocation.tool_id == "borrower_profile_lookup"
    assert invocation.status == "COMPLETED"
    assert timeline_entry.entry_type == "TOOL_INVOCATION_COMPLETED"
    assert timeline_entry.entry_metadata["replay_safe"] is True
    assert outbox_event.event_type == "tool.invocation_completed"
    assert outbox_event.publish_status == "PENDING"


async def test_record_tool_invocation_is_idempotent(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tools_activity, "SessionLocal", session_factory)
    monkeypatch.setattr(tools_activity, "publish_workflow_event", _no_publish)
    workflow_id = "00000000-0000-0000-0000-000000000101"
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        session.add(
            WorkflowRecord(
                workflow_id=workflow_id,
                workflow_type="MORTGAGE_EXCEPTION_REVIEW",
                state="DOCUMENT_ANALYSIS_PENDING",
                priority="NORMAL",
                correlation_id="tool-idempotency-test",
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
        await session.commit()

    payload = {
        "workflow_id": workflow_id,
        "correlation_id": "tool-idempotency-test",
        "tool_invocation_id": "00000000-0000-0000-0000-000000000201",
        "agent_execution_id": None,
        "agent_id": "document_analysis_agent",
        "tool_id": "document_fetch",
        "status": "COMPLETED",
        "permission_status": "AUTHORIZED",
        "input_validation_status": "VALIDATED",
        "output_validation_status": "VALIDATED",
        "input_metadata": {"requested_document_types": ["income_verification"]},
        "output_payload": {"available_document_types": ["income_verification"]},
        "execution_metadata": {"replay_safe": True},
        "error_message": None,
    }

    first = await tools_activity.record_tool_invocation(payload)
    second = await tools_activity.record_tool_invocation(payload)

    async with session_factory() as session:
        invocations = (await session.execute(select(ToolInvocationRecord))).scalars().all()
        timeline_entries = (await session.execute(select(WorkflowTimelineEntry))).scalars().all()
        outbox_events = (await session.execute(select(WorkflowEventOutbox))).scalars().all()

    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert len(invocations) == 1
    assert len(timeline_entries) == 1
    assert len(outbox_events) == 1


async def _no_publish(event_id: str) -> None:
    del event_id
