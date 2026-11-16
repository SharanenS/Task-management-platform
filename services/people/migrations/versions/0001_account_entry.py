"""Create the authoritative application account/profile boundary."""

import sqlalchemy as sa
from alembic import op

revision = "0001_account_entry"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("issuer", "subject", name="uq_account_identity"),
    )
    op.create_table(
        "employee_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("display_name", sa.String(150), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "company_role_grants",
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(16), primary_key=True),
        sa.UniqueConstraint("account_id", name="uq_account_company_role"),
        sa.CheckConstraint(
            "role IN ('ADMIN', 'MANAGER', 'EMPLOYEE', 'HR')", name="ck_company_role"
        ),
    )


def downgrade():
    op.drop_table("company_role_grants")
    op.drop_table("employee_profiles")
    op.drop_table("accounts")
