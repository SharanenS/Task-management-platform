"""Add durable execution attempts and bounded results."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261017_02"
down_revision: str | None = "20261016_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("result_content", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("result_content_type", sa.String(100), nullable=True))
    op.add_column("jobs", sa.Column("result_checksum", sa.String(64), nullable=True))
    op.add_column("jobs", sa.Column("result_row_count", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("result_truncated", sa.Boolean(), nullable=True))
    op.add_column("jobs", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("job_attempts", "created_at", new_column_name="started_at")
    op.add_column(
        "job_attempts", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("job_attempts", sa.Column("failure_code", sa.String(100), nullable=True))
    op.add_column(
        "job_attempts",
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("job_attempts", sa.Column("safe_summary", sa.String(500), nullable=True))


def downgrade() -> None:
    raise RuntimeError("Phase 7 migrations are forward-only.")
