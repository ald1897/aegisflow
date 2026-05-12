from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


json_type = JSON().with_variant(JSONB, "postgresql")


class WorkflowRecord(Base):
    __tablename__ = "workflow_records"

    workflow_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workflow_type: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(80), nullable=False)
    priority: Mapped[str] = mapped_column(String(40), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    workflow_metadata: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)
    temporal_workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    temporal_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    transitions: Mapped[list["WorkflowStateTransition"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
    )
    timeline_entries: Mapped[list["WorkflowTimelineEntry"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
    )
    outbox_events: Mapped[list["WorkflowEventOutbox"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
    )
    agent_executions: Mapped[list["AgentExecutionRecord"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
    )
    tool_invocations: Mapped[list["ToolInvocationRecord"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
    )
    approval_records: Mapped[list["ApprovalRecord"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
    )


class WorkflowStateTransition(Base):
    __tablename__ = "workflow_state_transitions"

    transition_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_records.workflow_id", ondelete="CASCADE"),
        nullable=False,
    )
    prior_state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    new_state: Mapped[str] = mapped_column(String(80), nullable=False)
    transition_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    workflow: Mapped[WorkflowRecord] = relationship(back_populates="transitions")


Index("ix_workflow_state_transitions_workflow_id", WorkflowStateTransition.workflow_id)


class WorkflowTimelineEntry(Base):
    __tablename__ = "workflow_timeline_entries"

    timeline_entry_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_records.workflow_id", ondelete="CASCADE"),
        nullable=False,
    )
    entry_type: Mapped[str] = mapped_column(String(80), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    entry_metadata: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    workflow: Mapped[WorkflowRecord] = relationship(back_populates="timeline_entries")


class WorkflowEventOutbox(Base):
    __tablename__ = "workflow_event_outbox"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    event_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1")
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_records.workflow_id", ondelete="CASCADE"),
        nullable=False,
    )
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)
    publish_status: Mapped[str] = mapped_column(String(40), nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workflow: Mapped[WorkflowRecord] = relationship(back_populates="outbox_events")


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
    input_metadata: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)
    output_payload: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)
    execution_metadata: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    workflow: Mapped[WorkflowRecord] = relationship(back_populates="agent_executions")


class ToolInvocationRecord(Base):
    __tablename__ = "tool_invocation_records"

    tool_invocation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_records.workflow_id", ondelete="CASCADE"),
        nullable=False,
    )
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
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
    input_metadata: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)
    output_payload: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)
    execution_metadata: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    workflow: Mapped[WorkflowRecord] = relationship(back_populates="tool_invocations")


class ApprovalRecord(Base):
    __tablename__ = "approval_records"

    approval_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_records.workflow_id", ondelete="CASCADE"),
        nullable=False,
    )
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    decision_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approval_metadata: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    workflow: Mapped[WorkflowRecord] = relationship(back_populates="approval_records")


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    evaluation_run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_records.workflow_id", ondelete="CASCADE"),
        nullable=False,
    )
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    evaluation_scope: Mapped[str] = mapped_column(String(80), nullable=False)
    evaluation_mode: Mapped[str] = mapped_column(String(80), nullable=False)
    dataset_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    run_metadata: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    evaluation_result_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    evaluation_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("evaluation_runs.evaluation_run_id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_records.workflow_id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_execution_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_execution_records.agent_execution_id", ondelete="SET NULL"),
        nullable=True,
    )
    prompt_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    evaluator_id: Mapped[str] = mapped_column(String(120), nullable=False)
    evaluator_version: Mapped[str] = mapped_column(String(40), nullable=False)
    score_name: Mapped[str] = mapped_column(String(120), nullable=False)
    score_value: Mapped[float] = mapped_column(Float, nullable=False)
    score_status: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(40), nullable=False)
    rationale: Mapped[str] = mapped_column(String(1000), nullable=False)
    result_metadata: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


Index("ix_workflow_timeline_entries_workflow_id", WorkflowTimelineEntry.workflow_id)
Index("ix_workflow_timeline_entries_created_at", WorkflowTimelineEntry.created_at)
Index("ix_workflow_event_outbox_workflow_id", WorkflowEventOutbox.workflow_id)
Index("ix_workflow_event_outbox_publish_status", WorkflowEventOutbox.publish_status)
Index("ix_agent_execution_records_workflow_id", AgentExecutionRecord.workflow_id)
Index("ix_agent_execution_records_agent_id", AgentExecutionRecord.agent_id)
Index("ix_tool_invocation_records_workflow_id", ToolInvocationRecord.workflow_id)
Index("ix_tool_invocation_records_agent_id", ToolInvocationRecord.agent_id)
Index("ix_tool_invocation_records_agent_execution_id", ToolInvocationRecord.agent_execution_id)
Index("ix_tool_invocation_records_tool_id", ToolInvocationRecord.tool_id)
Index("ix_approval_records_workflow_id", ApprovalRecord.workflow_id)
Index("ix_approval_records_reviewed_by", ApprovalRecord.reviewed_by)
Index("ix_approval_records_decision", ApprovalRecord.decision)
Index("ix_evaluation_runs_workflow_id", EvaluationRun.workflow_id)
Index("ix_evaluation_runs_dataset_id", EvaluationRun.dataset_id)
Index("ix_evaluation_runs_status", EvaluationRun.status)
Index("ix_evaluation_results_workflow_id", EvaluationResult.workflow_id)
Index("ix_evaluation_results_evaluation_run_id", EvaluationResult.evaluation_run_id)
Index("ix_evaluation_results_evaluator_id", EvaluationResult.evaluator_id)
Index("ix_evaluation_results_score_status", EvaluationResult.score_status)
