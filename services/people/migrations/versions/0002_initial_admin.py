"""Persist resumable initial-administrator provisioning ownership."""

import sqlalchemy as sa
from alembic import op

revision = "0002_initial_admin"
down_revision = "0001_account_entry"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "initial_admin_provisioning",
        sa.Column("key", sa.String(32), primary_key=True),
        sa.Column("operation_id", sa.String(36), nullable=False, unique=True),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("email_marker", sa.String(254), nullable=False),
        sa.Column("subject", sa.String(255), nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('PENDING_IDENTITY', 'IDENTITY_CREATED', 'COMPLETE')",
            name="ck_admin_provisioning_state",
        ),
    )


def downgrade():
    op.drop_table("initial_admin_provisioning")
