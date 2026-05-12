"""add approval records

Revision ID: 20260512_0005
Revises: 20260512_0004
Create Date: 2026-05-12 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260512_0005"
down_revision: str | None = "20260512_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approval_records",
        sa.Column("approval_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("decision_reason", sa.String(length=255), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.String(length=128), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "approval_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_records.workflow_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("approval_id"),
    )
    op.create_index("ix_approval_records_correlation_id", "approval_records", ["correlation_id"])
    op.create_index("ix_approval_records_decision", "approval_records", ["decision"])
    op.create_index("ix_approval_records_reviewed_by", "approval_records", ["reviewed_by"])
    op.create_index("ix_approval_records_workflow_id", "approval_records", ["workflow_id"])


def downgrade() -> None:
    op.drop_index("ix_approval_records_workflow_id", table_name="approval_records")
    op.drop_index("ix_approval_records_reviewed_by", table_name="approval_records")
    op.drop_index("ix_approval_records_decision", table_name="approval_records")
    op.drop_index("ix_approval_records_correlation_id", table_name="approval_records")
    op.drop_table("approval_records")
