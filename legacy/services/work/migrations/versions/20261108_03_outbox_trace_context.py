"""Add correlation_id and traceparent to work_outbox_events.

Revision ID: 20261108_03
Revises: 20261029_02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261108_03"
down_revision: str | None = "20261029_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("work_outbox_events", sa.Column("correlation_id", sa.String(64), nullable=True))
    op.add_column("work_outbox_events", sa.Column("traceparent", sa.String(64), nullable=True))


def downgrade() -> None:
    raise RuntimeError("Forward-only migrations are required")
