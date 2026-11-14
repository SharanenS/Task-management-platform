"""Add the task-completed event outbox.

Revision ID: 20261028_01
Revises: 20261015_02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261028_01"
down_revision: str | None = "20261015_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    status = postgresql.ENUM(
        "PENDING",
        "IN_FLIGHT",
        "PUBLISHED",
        "FAILED",
        name="work_event_status",
        create_type=False,
    )
    status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "work_outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("actor_employee_id", sa.Uuid(), nullable=False),
        sa.Column("task_version", sa.Integer(), nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.String(96), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_classification", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for name in (
        "event_type",
        "project_id",
        "task_id",
        "actor_employee_id",
        "status",
        "available_at",
        "created_at",
    ):
        op.create_index(f"ix_work_outbox_events_{name}", "work_outbox_events", [name])


def downgrade() -> None:
    raise RuntimeError("Forward-only migrations are required")
