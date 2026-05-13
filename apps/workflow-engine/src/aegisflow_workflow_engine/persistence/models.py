from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


json_type = JSON().with_variant(JSONB, "postgresql")


class WorkflowRecord(Base):
    __tablename__ = "workflow_records"

    workflow_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_type: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(80), nullable=False)
    priority: Mapped[str] = mapped_column(String(40), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    workflow_metadata: Mapped[dict] = mapped_column(json_type, nullable=False)
    temporal_workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    temporal_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowStateTransition(Base):
    __tablename__ = "workflow_state_transitions"

    transition_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_records.workflow_id", ondelete="CASCADE"),
        nullable=False,
    )
    prior_state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    new_state: Mapped[str] = mapped_column(String(80), nullable=False)
    transition_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowTimelineEntry(Base):
    __tablename__ = "workflow_timeline_entries"

    timeline_entry_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_records.workflow_id", ondelete="CASCADE"),
        nullable=False,
    )
    entry_type: Mapped[str] = mapped_column(String(80), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    entry_metadata: Mapped[dict] = mapped_column(json_type, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowEventOutbox(Base):
    __tablename__ = "workflow_event_outbox"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    event_version: Mapped[str] = mapped_column(String(20), nullable=False)
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_records.workflow_id", ondelete="CASCADE"),
        nullable=False,
    )
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(json_type, nullable=False)
    publish_status: Mapped[str] = mapped_column(String(40), nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentExecutionRecord(Base):
    __tablename__ = "agent_execution_records"

    agent_execution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_records.workflow_id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_id: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, nullable=False)
    input_metadata: Mapped[dict] = mapped_column(json_type, nullable=False)
    output_payload: Mapped[dict] = mapped_column(json_type, nullable=False)
    execution_metadata: Mapped[dict] = mapped_column(json_type, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ToolInvocationRecord(Base):
    __tablename__ = "tool_invocation_records"

    tool_invocation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_records.workflow_id", ondelete="CASCADE"),
        nullable=False,
    )
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_execution_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_execution_records.agent_execution_id", ondelete="SET NULL"),
        nullable=True,
    )
    agent_id: Mapped[str] = mapped_column(String(120), nullable=False)
    tool_id: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    permission_status: Mapped[str] = mapped_column(String(40), nullable=False)
    input_validation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    output_validation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    input_metadata: Mapped[dict] = mapped_column(json_type, nullable=False)
    output_payload: Mapped[dict] = mapped_column(json_type, nullable=False)
    execution_metadata: Mapped[dict] = mapped_column(json_type, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApprovalRecord(Base):
    __tablename__ = "approval_records"

    approval_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_records.workflow_id", ondelete="CASCADE"),
        nullable=False,
    )
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    decision_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approval_metadata: Mapped[dict] = mapped_column(json_type, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowReplayRun(Base):
    __tablename__ = "workflow_replay_runs"

    replay_run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_records.workflow_id", ondelete="CASCADE"),
        nullable=False,
    )
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    replay_mode: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    source_temporal_workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_temporal_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False)
    replay_metadata: Mapped[dict] = mapped_column(json_type, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowReplayStep(Base):
    __tablename__ = "workflow_replay_steps"

    replay_step_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    replay_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_replay_runs.replay_run_id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_records.workflow_id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(80), nullable=False)
    artifact_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    expected_state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    observed_state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    step_metadata: Mapped[dict] = mapped_column(json_type, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowRecoveryAction(Base):
    __tablename__ = "workflow_recovery_actions"

    recovery_action_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_records.workflow_id", ondelete="CASCADE"),
        nullable=False,
    )
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_resource_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_metadata: Mapped[dict] = mapped_column(json_type, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
