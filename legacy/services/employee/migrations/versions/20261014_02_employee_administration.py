"""Add employee administration state and idempotency records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261014_02"
down_revision: str | None = "20261012_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    status = postgresql.ENUM(
        "COMPLETE",
        "RECONCILIATION_REQUIRED",
        name="provisioning_status",
        create_type=False,
    )
    status.create(op.get_bind(), checkfirst=True)
    op.add_column("employees", sa.Column("username", sa.String(length=100), nullable=True))
    op.add_column(
        "employees",
        sa.Column(
            "provisioning_status",
            status,
            nullable=False,
            server_default="COMPLETE",
        ),
    )
    op.add_column(
        "employees", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    op.execute(
        """
        UPDATE employees
        SET username = lower(split_part(email, '@', 1)) || '-' || left(keycloak_subject, 8)
        WHERE username IS NULL
        """
    )
    op.alter_column("employees", "username", nullable=False)
    op.create_index("ix_employees_username", "employees", ["username"], unique=True)
    op.create_index("ix_employees_email", "employees", ["email"], unique=True)
    op.create_table(
        "provisioning_requests",
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("idempotency_key"),
        sa.UniqueConstraint("employee_id"),
    )


def downgrade() -> None:
    op.drop_table("provisioning_requests")
    op.drop_index("ix_employees_email", table_name="employees")
    op.drop_index("ix_employees_username", table_name="employees")
    op.drop_column("employees", "version")
    op.drop_column("employees", "provisioning_status")
    op.drop_column("employees", "username")
    postgresql.ENUM(name="provisioning_status").drop(op.get_bind(), checkfirst=True)
