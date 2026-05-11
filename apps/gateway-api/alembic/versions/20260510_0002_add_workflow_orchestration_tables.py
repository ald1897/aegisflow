"""add workflow orchestration tables

Revision ID: 20260510_0002
Revises: 20260510_0001
Create Date: 2026-05-10 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260510_0002"
down_revision: str | None = "20260510_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workflow_records", sa.Column("temporal_workflow_id", sa.String(length=255), nullable=True))
    op.add_column("workflow_records", sa.Column("temporal_run_id", sa.String(length=255), nullable=True))
    op.add_column("workflow_records", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workflow_records", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workflow_records", sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_workflow_records_temporal_workflow_id", "workflow_records", ["temporal_workflow_id"])

    op.create_table(
        "workflow_timeline_entries",
        sa.Column("timeline_entry_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("entry_type", sa.String(length=80), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("state", sa.String(length=80), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column(
            "entry_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_records.workflow_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("timeline_entry_id"),
    )
    op.create_index(
        "ix_workflow_timeline_entries_correlation_id",
        "workflow_timeline_entries",
        ["correlation_id"],
    )
    op.create_index(
        "ix_workflow_timeline_entries_created_at",
        "workflow_timeline_entries",
        ["created_at"],
    )
    op.create_index(
        "ix_workflow_timeline_entries_workflow_id",
        "workflow_timeline_entries",
        ["workflow_id"],
    )

    op.create_table(
        "workflow_event_outbox",
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("event_version", sa.String(length=20), nullable=False),
        sa.Column("workflow_id", sa.String(length=36), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("publish_status", sa.String(length=40), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_records.workflow_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_workflow_event_outbox_correlation_id", "workflow_event_outbox", ["correlation_id"])
    op.create_index("ix_workflow_event_outbox_publish_status", "workflow_event_outbox", ["publish_status"])
    op.create_index("ix_workflow_event_outbox_workflow_id", "workflow_event_outbox", ["workflow_id"])


def downgrade() -> None:
    op.drop_index("ix_workflow_event_outbox_workflow_id", table_name="workflow_event_outbox")
    op.drop_index("ix_workflow_event_outbox_publish_status", table_name="workflow_event_outbox")
    op.drop_index("ix_workflow_event_outbox_correlation_id", table_name="workflow_event_outbox")
    op.drop_table("workflow_event_outbox")

    op.drop_index("ix_workflow_timeline_entries_workflow_id", table_name="workflow_timeline_entries")
    op.drop_index("ix_workflow_timeline_entries_created_at", table_name="workflow_timeline_entries")
    op.drop_index("ix_workflow_timeline_entries_correlation_id", table_name="workflow_timeline_entries")
    op.drop_table("workflow_timeline_entries")

    op.drop_index("ix_workflow_records_temporal_workflow_id", table_name="workflow_records")
    op.drop_column("workflow_records", "failed_at")
    op.drop_column("workflow_records", "completed_at")
    op.drop_column("workflow_records", "started_at")
    op.drop_column("workflow_records", "temporal_run_id")
    op.drop_column("workflow_records", "temporal_workflow_id")
