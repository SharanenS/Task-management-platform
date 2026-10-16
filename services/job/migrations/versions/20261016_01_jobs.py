"""Create durable jobs and attempt-history foundation.

Revision ID: 20261016_01
Revises:
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261016_01"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    job_type = sa.Enum("PROJECT_TASK_EXPORT", name="job_type")
    job_status = sa.Enum(
        "SUBMITTED", "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED", name="job_status"
    )
    attempt_status = sa.Enum(
        "SUBMITTED",
        "QUEUED",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
        name="job_attempt_status",
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_type", job_type, nullable=False),
        sa.Column("status", job_status, nullable=False),
        sa.Column("submitter_employee_id", sa.Uuid(), nullable=False),
        sa.Column("related_project_id", sa.Uuid(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("result_summary", sa.String(500), nullable=True),
        sa.Column("failure_classification", sa.String(100), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("submitter_employee_id", "idempotency_key", name="uq_job_actor_key"),
    )
    op.create_index("ix_jobs_submitter_employee_id", "jobs", ["submitter_employee_id"])
    op.create_index("ix_jobs_related_project_id", "jobs", ["related_project_id"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])
    op.create_table(
        "job_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "job_id", sa.Uuid(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", attempt_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_job_attempt_number"),
    )
    op.create_index("ix_job_attempts_job_id", "job_attempts", ["job_id"])


def downgrade() -> None:
    raise RuntimeError("Phase 6 migrations are forward-only.")
