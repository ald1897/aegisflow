"""add agent execution records

Revision ID: 20260510_0003
Revises: 20260510_0002
Create Date: 2026-05-10 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260510_0003"
down_revision: str | None = "20260510_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_execution_records",
        sa.Column("agent_execution_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=120), nullable=False),
        sa.Column("prompt_id", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("validation_status", sa.String(length=40), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False),
        sa.Column(
            "input_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "output_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "execution_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_records.workflow_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("agent_execution_id"),
    )
    op.create_index("ix_agent_execution_records_agent_id", "agent_execution_records", ["agent_id"])
    op.create_index("ix_agent_execution_records_correlation_id", "agent_execution_records", ["correlation_id"])
    op.create_index("ix_agent_execution_records_workflow_id", "agent_execution_records", ["workflow_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_execution_records_workflow_id", table_name="agent_execution_records")
    op.drop_index("ix_agent_execution_records_correlation_id", table_name="agent_execution_records")
    op.drop_index("ix_agent_execution_records_agent_id", table_name="agent_execution_records")
    op.drop_table("agent_execution_records")
