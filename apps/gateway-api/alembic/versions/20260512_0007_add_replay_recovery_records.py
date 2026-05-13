"""add replay and recovery records

Revision ID: 20260512_0007
Revises: 20260512_0006
Create Date: 2026-05-12 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260512_0007"
down_revision: str | None = "20260512_0006"
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
        "workflow_replay_runs",
        sa.Column("replay_run_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("replay_mode", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("source_temporal_workflow_id", sa.String(length=255), nullable=True),
        sa.Column("source_temporal_run_id", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        _jsonb_column("replay_metadata"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_records.workflow_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("replay_run_id"),
    )
    op.create_index("ix_workflow_replay_runs_correlation_id", "workflow_replay_runs", ["correlation_id"])
    op.create_index("ix_workflow_replay_runs_replay_mode", "workflow_replay_runs", ["replay_mode"])
    op.create_index("ix_workflow_replay_runs_status", "workflow_replay_runs", ["status"])
    op.create_index(
        "ix_workflow_replay_runs_source_temporal_workflow_id",
        "workflow_replay_runs",
        ["source_temporal_workflow_id"],
    )
    op.create_index("ix_workflow_replay_runs_workflow_id", "workflow_replay_runs", ["workflow_id"])

    op.create_table(
        "workflow_replay_steps",
        sa.Column("replay_step_id", sa.String(length=36), nullable=False),
        sa.Column("replay_run_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=80), nullable=False),
        sa.Column("artifact_id", sa.String(length=128), nullable=True),
        sa.Column("expected_state", sa.String(length=80), nullable=True),
        sa.Column("observed_state", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=False),
        _jsonb_column("step_metadata"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["replay_run_id"], ["workflow_replay_runs.replay_run_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_records.workflow_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("replay_step_id"),
        sa.UniqueConstraint("replay_run_id", "sequence_number", name="uq_workflow_replay_steps_run_sequence"),
    )
    op.create_index("ix_workflow_replay_steps_artifact_type", "workflow_replay_steps", ["artifact_type"])
    op.create_index("ix_workflow_replay_steps_replay_run_id", "workflow_replay_steps", ["replay_run_id"])
    op.create_index("ix_workflow_replay_steps_status", "workflow_replay_steps", ["status"])
    op.create_index("ix_workflow_replay_steps_workflow_id", "workflow_replay_steps", ["workflow_id"])

    op.create_table(
        "workflow_recovery_actions",
        sa.Column("recovery_action_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("target_resource_type", sa.String(length=80), nullable=False),
        sa.Column("target_resource_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        _jsonb_column("result_metadata"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_records.workflow_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("recovery_action_id"),
    )
    op.create_index("ix_workflow_recovery_actions_action_type", "workflow_recovery_actions", ["action_type"])
    op.create_index("ix_workflow_recovery_actions_correlation_id", "workflow_recovery_actions", ["correlation_id"])
    op.create_index("ix_workflow_recovery_actions_status", "workflow_recovery_actions", ["status"])
    op.create_index(
        "ix_workflow_recovery_actions_target",
        "workflow_recovery_actions",
        ["target_resource_type", "target_resource_id"],
    )
    op.create_index("ix_workflow_recovery_actions_workflow_id", "workflow_recovery_actions", ["workflow_id"])


def downgrade() -> None:
    op.drop_index("ix_workflow_recovery_actions_workflow_id", table_name="workflow_recovery_actions")
    op.drop_index("ix_workflow_recovery_actions_target", table_name="workflow_recovery_actions")
    op.drop_index("ix_workflow_recovery_actions_status", table_name="workflow_recovery_actions")
    op.drop_index("ix_workflow_recovery_actions_correlation_id", table_name="workflow_recovery_actions")
    op.drop_index("ix_workflow_recovery_actions_action_type", table_name="workflow_recovery_actions")
    op.drop_table("workflow_recovery_actions")

    op.drop_index("ix_workflow_replay_steps_workflow_id", table_name="workflow_replay_steps")
    op.drop_index("ix_workflow_replay_steps_status", table_name="workflow_replay_steps")
    op.drop_index("ix_workflow_replay_steps_replay_run_id", table_name="workflow_replay_steps")
    op.drop_index("ix_workflow_replay_steps_artifact_type", table_name="workflow_replay_steps")
    op.drop_table("workflow_replay_steps")

    op.drop_index("ix_workflow_replay_runs_workflow_id", table_name="workflow_replay_runs")
    op.drop_index("ix_workflow_replay_runs_source_temporal_workflow_id", table_name="workflow_replay_runs")
    op.drop_index("ix_workflow_replay_runs_status", table_name="workflow_replay_runs")
    op.drop_index("ix_workflow_replay_runs_replay_mode", table_name="workflow_replay_runs")
    op.drop_index("ix_workflow_replay_runs_correlation_id", table_name="workflow_replay_runs")
    op.drop_table("workflow_replay_runs")
