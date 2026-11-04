"""Create notification inbox and recipient-owned notifications.

Revision ID: 20261029_01
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inbox = sa.Enum("RECEIVED", "PROCESSED", "QUARANTINED", name="notification_inbox_status")
    category = sa.Enum(
        "TASK_ASSIGNED", "REPORT_SUCCEEDED", "REPORT_FAILED", name="notification_type"
    )
    op.create_table(
        "notification_source_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("status", inbox, nullable=False),
        sa.Column("failure_classification", sa.String(64)),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("recipient_employee_id", sa.Uuid(), nullable=False),
        sa.Column("notification_type", category, nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column(
            "source_event_id",
            sa.Uuid(),
            sa.ForeignKey("notification_source_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("project_id", sa.Uuid()),
        sa.Column("task_id", sa.Uuid()),
        sa.Column("report_id", sa.Uuid()),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "recipient_employee_id", "source_event_id", name="uq_notification_recipient_event"
        ),
    )
    op.create_index(
        "ix_notifications_recipient_employee_id", "notifications", ["recipient_employee_id"]
    )
    op.create_index("ix_notifications_source_event_id", "notifications", ["source_event_id"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_index(
        "ix_notifications_recipient_created",
        "notifications",
        ["recipient_employee_id", "created_at", "id"],
    )
    op.create_index(
        "ix_notifications_recipient_unread",
        "notifications",
        ["recipient_employee_id", "read_at", "created_at"],
    )


def downgrade() -> None:
    raise RuntimeError("Forward-only migrations are required")
