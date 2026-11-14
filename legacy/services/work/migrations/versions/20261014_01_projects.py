"""Create projects and memberships.

Revision ID: 20261014_01
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "20261014_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    status = sa.Enum("DRAFT", "ACTIVE", "ARCHIVED", name="project_status")
    role = sa.Enum("PROJECT_MANAGER", "CONTRIBUTOR", name="project_role")
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("key", sa.String(32), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", status, nullable=False),
        sa.Column("creator_employee_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_projects_key", "projects", ["key"], unique=True)
    op.create_index("ix_projects_creator_employee_id", "projects", ["creator_employee_id"])
    op.create_table(
        "project_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE")),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("role", role, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "employee_id"),
    )
    op.create_index("ix_project_memberships_project_id", "project_memberships", ["project_id"])
    op.create_index("ix_project_memberships_employee_id", "project_memberships", ["employee_id"])


def downgrade() -> None:
    op.drop_table("project_memberships")
    op.drop_table("projects")
    sa.Enum(name="project_role").drop(op.get_bind())
    sa.Enum(name="project_status").drop(op.get_bind())
