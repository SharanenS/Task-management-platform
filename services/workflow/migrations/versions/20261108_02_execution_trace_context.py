"""Add correlation_id and traceparent to workflow_executions.

Revision ID: 20261108_02
Revises: 20261028_01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261108_02"
down_revision: str | None = "20261028_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workflow_executions", sa.Column("correlation_id", sa.String(64), nullable=True))
    op.add_column("workflow_executions", sa.Column("traceparent", sa.String(64), nullable=True))


def downgrade() -> None:
    raise RuntimeError("Forward-only migrations are required")
