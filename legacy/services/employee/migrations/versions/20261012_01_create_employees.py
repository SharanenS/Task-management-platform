"""Create employee profiles."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261012_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    role = postgresql.ENUM("ADMIN", "MANAGER", "MEMBER", name="application_role", create_type=False)
    role.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "employees",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("keycloak_subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("role", role, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_employees_keycloak_subject", "employees", ["keycloak_subject"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_employees_keycloak_subject", table_name="employees")
    op.drop_table("employees")
    postgresql.ENUM(name="application_role").drop(op.get_bind(), checkfirst=True)
