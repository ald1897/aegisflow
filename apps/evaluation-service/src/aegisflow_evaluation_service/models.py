from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, UniqueConstraint
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

    workflow_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    evaluation_runs: Mapped[list["EvaluationRun"]] = relationship(back_populates="workflow")
    evaluation_results: Mapped[list["EvaluationResult"]] = relationship(back_populates="workflow")


class AgentExecutionRecord(Base):
    __tablename__ = "agent_execution_records"

    agent_execution_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    evaluation_results: Mapped[list["EvaluationResult"]] = relationship(back_populates="agent_execution")


class EvaluationDatasetCase(Base):
    __tablename__ = "evaluation_dataset_cases"
    __table_args__ = (
        UniqueConstraint("dataset_id", "case_name", name="uq_evaluation_dataset_cases_dataset_case_name"),
    )

    dataset_case_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(120), nullable=False)
    case_name: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_type: Mapped[str] = mapped_column(String(80), nullable=False)
    expected_agents: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)
    expected_tools: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)
    expected_human_review: Mapped[bool] = mapped_column(Boolean, nullable=False)
    expected_decision: Mapped[str | None] = mapped_column(String(40), nullable=True)
    expected_signals: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)
    case_metadata: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


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

    workflow: Mapped[WorkflowRecord] = relationship(back_populates="evaluation_runs")
    results: Mapped[list["EvaluationResult"]] = relationship(
        back_populates="evaluation_run",
        cascade="all, delete-orphan",
    )


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

    evaluation_run: Mapped[EvaluationRun] = relationship(back_populates="results")
    workflow: Mapped[WorkflowRecord] = relationship(back_populates="evaluation_results")
    agent_execution: Mapped[AgentExecutionRecord | None] = relationship(back_populates="evaluation_results")


Index("ix_evaluation_dataset_cases_dataset_id", EvaluationDatasetCase.dataset_id)
Index("ix_evaluation_dataset_cases_workflow_type", EvaluationDatasetCase.workflow_type)
Index("ix_evaluation_runs_dataset_id", EvaluationRun.dataset_id)
Index("ix_evaluation_runs_status", EvaluationRun.status)
Index("ix_evaluation_runs_workflow_id", EvaluationRun.workflow_id)
Index("ix_evaluation_results_agent_execution_id", EvaluationResult.agent_execution_id)
Index("ix_evaluation_results_evaluation_run_id", EvaluationResult.evaluation_run_id)
Index("ix_evaluation_results_evaluator_id", EvaluationResult.evaluator_id)
Index("ix_evaluation_results_score_name", EvaluationResult.score_name)
Index("ix_evaluation_results_score_status", EvaluationResult.score_status)
Index("ix_evaluation_results_severity", EvaluationResult.severity)
Index("ix_evaluation_results_workflow_id", EvaluationResult.workflow_id)
