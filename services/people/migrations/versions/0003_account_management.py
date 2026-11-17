"""Durable account provisioning and administrator change history."""

import sqlalchemy as sa
from alembic import op

revision = "0003_account_management"
down_revision = "0002_initial_admin"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "accounts",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "account_provisioning",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("display_name", sa.String(150), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(255)),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
        ),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("failure_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "account_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), nullable=False, unique=True),
        sa.Column(
            "actor_id",
            sa.String(36),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "target_id",
            sa.String(36),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "operation_id",
            sa.String(36),
            sa.ForeignKey("account_provisioning.id", ondelete="RESTRICT"),
        ),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("before", sa.Text(), nullable=False),
        sa.Column("after", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("account_audit")
    op.drop_table("account_provisioning")
    op.drop_column("accounts", "version")
