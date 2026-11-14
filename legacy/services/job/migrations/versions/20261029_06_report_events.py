"""Add terminal report domain outbox.

Revision ID: 20261029_06
Revises: 20261020_05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_06"
down_revision: str | None = "20261020_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    status = sa.Enum("PENDING", "IN_FLIGHT", "PUBLISHED", "FAILED", name="job_domain_event_status")
    op.create_table(
        "job_domain_outbox",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "job_id", sa.Uuid(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("recipient_employee_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid()),
        sa.Column("status", status, nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.String(96)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("last_failure_classification", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", "event_type", name="uq_job_domain_terminal_event"),
    )
    op.create_index("ix_job_domain_outbox_job_id", "job_domain_outbox", ["job_id"])
    op.create_index(
        "ix_job_domain_outbox_recipient_employee_id", "job_domain_outbox", ["recipient_employee_id"]
    )
    op.create_index(
        "ix_job_domain_claim",
        "job_domain_outbox",
        ["status", "available_at", "lease_expires_at", "created_at", "id"],
    )


def downgrade() -> None:
    raise RuntimeError("Forward-only migrations are required")
