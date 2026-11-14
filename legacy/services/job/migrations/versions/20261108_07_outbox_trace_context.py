"""Add correlation_id and traceparent to jobs, job_publication_outbox, and job_domain_outbox.

Revision ID: 20261108_07
Revises: 20261029_06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261108_07"
down_revision: str | None = "20261029_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("correlation_id", sa.String(64), nullable=True))
    op.add_column("jobs", sa.Column("traceparent", sa.String(64), nullable=True))

    op.add_column(
        "job_publication_outbox", sa.Column("correlation_id", sa.String(64), nullable=True)
    )
    op.add_column("job_publication_outbox", sa.Column("traceparent", sa.String(64), nullable=True))

    op.add_column("job_domain_outbox", sa.Column("correlation_id", sa.String(64), nullable=True))
    op.add_column("job_domain_outbox", sa.Column("traceparent", sa.String(64), nullable=True))


def downgrade() -> None:
    raise RuntimeError("Forward-only migrations are required")
