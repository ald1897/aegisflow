"""add tool invocation records

Revision ID: 20260512_0004
Revises: 20260510_0003
Create Date: 2026-05-12 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260512_0004"
down_revision: str | None = "20260510_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tool_invocation_records",
        sa.Column("tool_invocation_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("agent_execution_id", sa.String(length=36), nullable=True),
        sa.Column("agent_id", sa.String(length=120), nullable=False),
        sa.Column("tool_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("permission_status", sa.String(length=40), nullable=False),
        sa.Column("input_validation_status", sa.String(length=40), nullable=False),
        sa.Column("output_validation_status", sa.String(length=40), nullable=False),
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
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_records.workflow_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["agent_execution_id"],
            ["agent_execution_records.agent_execution_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("tool_invocation_id"),
    )
    op.create_index("ix_tool_invocation_records_agent_execution_id", "tool_invocation_records", ["agent_execution_id"])
    op.create_index("ix_tool_invocation_records_agent_id", "tool_invocation_records", ["agent_id"])
    op.create_index("ix_tool_invocation_records_correlation_id", "tool_invocation_records", ["correlation_id"])
    op.create_index("ix_tool_invocation_records_tool_id", "tool_invocation_records", ["tool_id"])
    op.create_index("ix_tool_invocation_records_workflow_id", "tool_invocation_records", ["workflow_id"])


def downgrade() -> None:
    op.drop_index("ix_tool_invocation_records_workflow_id", table_name="tool_invocation_records")
    op.drop_index("ix_tool_invocation_records_tool_id", table_name="tool_invocation_records")
    op.drop_index("ix_tool_invocation_records_correlation_id", table_name="tool_invocation_records")
    op.drop_index("ix_tool_invocation_records_agent_id", table_name="tool_invocation_records")
    op.drop_index("ix_tool_invocation_records_agent_execution_id", table_name="tool_invocation_records")
    op.drop_table("tool_invocation_records")
