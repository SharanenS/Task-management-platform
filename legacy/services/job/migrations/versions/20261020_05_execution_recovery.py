"""Add fenced execution leases and generation-scoped publication."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261020_05"
down_revision: str | None = "20261020_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE job_attempt_status ADD VALUE IF NOT EXISTS 'ABANDONED'")
    op.add_column(
        "jobs", sa.Column("execution_generation", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "jobs",
        sa.Column("retry_exhausted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "jobs", sa.Column("manual_retry_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "job_publication_outbox",
        sa.Column("execution_generation", sa.Integer(), nullable=False, server_default="1"),
    )
    op.drop_constraint("uq_job_publication_event", "job_publication_outbox", type_="unique")
    op.create_unique_constraint(
        "uq_job_publication_generation",
        "job_publication_outbox",
        ["job_id", "execution_generation", "event_type"],
    )
    op.add_column(
        "job_attempts",
        sa.Column("execution_generation", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "job_attempts",
        sa.Column("execution_fence", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("job_attempts", sa.Column("execution_lease_token", sa.String(64)))
    op.add_column("job_attempts", sa.Column("lease_acquired_at", sa.DateTime(timezone=True)))
    op.add_column("job_attempts", sa.Column("lease_expires_at", sa.DateTime(timezone=True)))
    op.add_column("job_attempts", sa.Column("last_heartbeat_at", sa.DateTime(timezone=True)))
    op.add_column("job_attempts", sa.Column("abandoned_at", sa.DateTime(timezone=True)))
    op.add_column("job_attempts", sa.Column("retry_scheduled_at", sa.DateTime(timezone=True)))
    op.add_column("job_attempts", sa.Column("recovered_at", sa.DateTime(timezone=True)))
    op.execute("""
        UPDATE jobs SET execution_generation = 1
        WHERE EXISTS (SELECT 1 FROM job_publication_outbox o WHERE o.job_id = jobs.id)
    """)
    op.execute("""
        UPDATE job_attempts
        SET execution_generation = 1, execution_fence = attempt_number
    """)
    op.create_index(
        "ix_job_attempt_recovery",
        "job_attempts",
        ["status", "lease_expires_at", "id"],
    )


def downgrade() -> None:
    raise RuntimeError("Phase 9 migrations are forward-only.")
