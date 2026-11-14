"""Add the durable retry-scheduled attempt status."""

from collections.abc import Sequence

from alembic import op

revision: str = "20261020_03"
down_revision: str | None = "20261017_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE job_attempt_status ADD VALUE IF NOT EXISTS 'RETRY_SCHEDULED'")


def downgrade() -> None:
    raise RuntimeError("Phase 7 migrations are forward-only.")
