"""Require one logical notification per source event.

Revision ID: 20261029_02
Revises: 20261029_01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261029_02"
down_revision: str | None = "20261029_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_notification_source_event", "notifications", ["source_event_id"]
    )


def downgrade() -> None:
    raise RuntimeError("Forward-only migrations are required")
