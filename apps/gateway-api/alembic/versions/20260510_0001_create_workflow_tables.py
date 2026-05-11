"""create workflow tables

Revision ID: 20260510_0001
Revises:
Create Date: 2026-05-10 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260510_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_records",
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_type", sa.String(length=80), nullable=False),
        sa.Column("state", sa.String(length=80), nullable=False),
        sa.Column("priority", sa.String(length=40), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column(
            "workflow_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("workflow_id"),
    )
    op.create_index("ix_workflow_records_correlation_id", "workflow_records", ["correlation_id"])

    op.create_table(
        "workflow_state_transitions",
        sa.Column("transition_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("prior_state", sa.String(length=80), nullable=True),
        sa.Column("new_state", sa.String(length=80), nullable=False),
        sa.Column("transition_reason", sa.String(length=255), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_records.workflow_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("transition_id"),
    )
    op.create_index(
        "ix_workflow_state_transitions_correlation_id",
        "workflow_state_transitions",
        ["correlation_id"],
    )
    op.create_index(
        "ix_workflow_state_transitions_workflow_id",
        "workflow_state_transitions",
        ["workflow_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_state_transitions_workflow_id", table_name="workflow_state_transitions")
    op.drop_index("ix_workflow_state_transitions_correlation_id", table_name="workflow_state_transitions")
    op.drop_table("workflow_state_transitions")
    op.drop_index("ix_workflow_records_correlation_id", table_name="workflow_records")
    op.drop_table("workflow_records")
