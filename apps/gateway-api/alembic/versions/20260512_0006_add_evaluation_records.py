"""add evaluation records

Revision ID: 20260512_0006
Revises: 20260512_0005
Create Date: 2026-05-12 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260512_0006"
down_revision: str | None = "20260512_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _jsonb_column(name: str) -> sa.Column:
    return sa.Column(
        name,
        postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )


def upgrade() -> None:
    op.create_table(
        "evaluation_dataset_cases",
        sa.Column("dataset_case_id", sa.String(length=128), nullable=False),
        sa.Column("dataset_id", sa.String(length=120), nullable=False),
        sa.Column("case_name", sa.String(length=255), nullable=False),
        sa.Column("workflow_type", sa.String(length=80), nullable=False),
        _jsonb_column("expected_agents"),
        _jsonb_column("expected_tools"),
        sa.Column("expected_human_review", sa.Boolean(), nullable=False),
        sa.Column("expected_decision", sa.String(length=40), nullable=True),
        _jsonb_column("expected_signals"),
        _jsonb_column("case_metadata"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("dataset_case_id"),
        sa.UniqueConstraint("dataset_id", "case_name", name="uq_evaluation_dataset_cases_dataset_case_name"),
    )
    op.create_index("ix_evaluation_dataset_cases_dataset_id", "evaluation_dataset_cases", ["dataset_id"])
    op.create_index("ix_evaluation_dataset_cases_workflow_type", "evaluation_dataset_cases", ["workflow_type"])

    op.create_table(
        "evaluation_runs",
        sa.Column("evaluation_run_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("evaluation_scope", sa.String(length=80), nullable=False),
        sa.Column("evaluation_mode", sa.String(length=80), nullable=False),
        sa.Column("dataset_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        _jsonb_column("run_metadata"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_records.workflow_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("evaluation_run_id"),
    )
    op.create_index("ix_evaluation_runs_correlation_id", "evaluation_runs", ["correlation_id"])
    op.create_index("ix_evaluation_runs_dataset_id", "evaluation_runs", ["dataset_id"])
    op.create_index("ix_evaluation_runs_status", "evaluation_runs", ["status"])
    op.create_index("ix_evaluation_runs_workflow_id", "evaluation_runs", ["workflow_id"])

    op.create_table(
        "evaluation_results",
        sa.Column("evaluation_result_id", sa.String(length=36), nullable=False),
        sa.Column("evaluation_run_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("agent_execution_id", sa.String(length=36), nullable=True),
        sa.Column("prompt_id", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=40), nullable=True),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("evaluator_id", sa.String(length=120), nullable=False),
        sa.Column("evaluator_version", sa.String(length=40), nullable=False),
        sa.Column("score_name", sa.String(length=120), nullable=False),
        sa.Column("score_value", sa.Float(), nullable=False),
        sa.Column("score_status", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("rationale", sa.String(length=1000), nullable=False),
        _jsonb_column("result_metadata"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["evaluation_run_id"], ["evaluation_runs.evaluation_run_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_records.workflow_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["agent_execution_id"],
            ["agent_execution_records.agent_execution_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("evaluation_result_id"),
    )
    op.create_index("ix_evaluation_results_agent_execution_id", "evaluation_results", ["agent_execution_id"])
    op.create_index("ix_evaluation_results_evaluation_run_id", "evaluation_results", ["evaluation_run_id"])
    op.create_index("ix_evaluation_results_evaluator_id", "evaluation_results", ["evaluator_id"])
    op.create_index("ix_evaluation_results_score_name", "evaluation_results", ["score_name"])
    op.create_index("ix_evaluation_results_score_status", "evaluation_results", ["score_status"])
    op.create_index("ix_evaluation_results_severity", "evaluation_results", ["severity"])
    op.create_index("ix_evaluation_results_workflow_id", "evaluation_results", ["workflow_id"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_results_workflow_id", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_severity", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_score_status", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_score_name", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_evaluator_id", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_evaluation_run_id", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_agent_execution_id", table_name="evaluation_results")
    op.drop_table("evaluation_results")

    op.drop_index("ix_evaluation_runs_workflow_id", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_status", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_dataset_id", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_correlation_id", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")

    op.drop_index("ix_evaluation_dataset_cases_workflow_type", table_name="evaluation_dataset_cases")
    op.drop_index("ix_evaluation_dataset_cases_dataset_id", table_name="evaluation_dataset_cases")
    op.drop_table("evaluation_dataset_cases")
