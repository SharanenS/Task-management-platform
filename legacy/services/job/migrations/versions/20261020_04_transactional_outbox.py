"""Add transactional publication outbox."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261020_04"
down_revision: str | None = "20261020_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    status = postgresql.ENUM(
        "PENDING",
        "IN_FLIGHT",
        "PUBLISHED",
        "FAILED",
        "RECONCILIATION_REQUIRED",
        name="publication_status",
        create_type=False,
    )
    status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "job_publication_outbox",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "job_id", sa.Uuid(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("event_type", sa.String(50), nullable=False, server_default="EXECUTE_JOB"),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", status, nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("lease_token", sa.String(64)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("last_failure_classification", sa.String(50)),
        sa.UniqueConstraint("job_id", "event_type", name="uq_job_publication_event"),
    )
    op.create_index("ix_job_publication_outbox_job_id", "job_publication_outbox", ["job_id"])
    op.create_index(
        "ix_job_publication_claim",
        "job_publication_outbox",
        ["status", "available_at", "lease_expires_at", "created_at", "id"],
    )
    op.execute("""
        INSERT INTO job_publication_outbox
          (id, job_id, event_type, schema_version, status, available_at,
           created_at, updated_at, published_at)
        SELECT gen_random_uuid(), id, 'EXECUTE_JOB', 1,
          CASE WHEN status::text = 'QUEUED'
            THEN 'RECONCILIATION_REQUIRED'::publication_status
            ELSE 'PUBLISHED'::publication_status END,
          updated_at, updated_at, updated_at,
          CASE WHEN status::text IN ('RUNNING','SUCCEEDED','FAILED') THEN updated_at ELSE NULL END
        FROM jobs WHERE status::text IN ('QUEUED','RUNNING','SUCCEEDED','FAILED')
    """)


def downgrade() -> None:
    raise RuntimeError("Phase 8 migrations are forward-only.")
