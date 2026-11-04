"""Add task-assignment event recipients.

Revision ID: 20261029_02
Revises: 20261028_01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_02"
down_revision: str | None = "20261028_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("work_outbox_events", sa.Column("recipient_employee_id", sa.Uuid()))
    op.create_index(
        "ix_work_outbox_events_recipient_employee_id",
        "work_outbox_events",
        ["recipient_employee_id"],
    )


def downgrade() -> None:
    raise RuntimeError("Forward-only migrations are required")
