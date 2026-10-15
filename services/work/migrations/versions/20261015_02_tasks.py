"""Add task management.

Revision ID: 20261015_02
Revises: 20261014_01
"""

import sqlalchemy as sa
from alembic import op

revision = "20261015_02"
down_revision = "20261014_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    task_status = sa.Enum("TODO", "IN_PROGRESS", "BLOCKED", "DONE", "CANCELLED", name="task_status")
    task_priority = sa.Enum("LOW", "MEDIUM", "HIGH", "URGENT", name="task_priority")
    activity_type = sa.Enum(
        "CREATED",
        "METADATA_UPDATED",
        "ASSIGNMENT_CHANGED",
        "STATUS_CHANGED",
        "COMMENT_ADDED",
        name="task_activity_type",
    )
    op.add_column(
        "projects", sa.Column("next_task_number", sa.Integer(), nullable=False, server_default="1")
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", task_status, nullable=False),
        sa.Column("priority", task_priority, nullable=False),
        sa.Column("assignee_employee_id", sa.Uuid(), nullable=True),
        sa.Column("creator_employee_id", sa.Uuid(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number"),
    )
    for column in (
        "project_id",
        "status",
        "priority",
        "assignee_employee_id",
        "creator_employee_id",
        "created_at",
    ):
        op.create_index(f"ix_tasks_{column}", "tasks", [column])
    op.create_table(
        "task_comments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("author_employee_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("task_id", "author_employee_id", "created_at"):
        op.create_index(f"ix_task_comments_{column}", "task_comments", [column])
    op.create_table(
        "task_activities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("actor_employee_id", sa.Uuid(), nullable=False),
        sa.Column("activity_type", activity_type, nullable=False),
        sa.Column("change_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("task_id", "actor_employee_id", "activity_type", "created_at"):
        op.create_index(f"ix_task_activities_{column}", "task_activities", [column])


def downgrade() -> None:
    op.drop_table("task_activities")
    op.drop_table("task_comments")
    op.drop_table("tasks")
    op.drop_column("projects", "next_task_number")
    sa.Enum(name="task_activity_type").drop(op.get_bind())
    sa.Enum(name="task_priority").drop(op.get_bind())
    sa.Enum(name="task_status").drop(op.get_bind())
