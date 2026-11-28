"""Add retained task schedules, dependency edges and confirmed revision history."""

import sqlalchemy as sa
from alembic import op

revision = "0007_task_scheduling"
down_revision = "0006_task_breakdown"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "task_schedules",
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("work_tasks.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("requested_start", sa.String(10), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column(
            "calendar_version_id",
            sa.String(36),
            sa.ForeignKey("calendar_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("original", sa.Text(), nullable=False),
        sa.Column("current", sa.Text(), nullable=False),
        sa.CheckConstraint("duration >= 1 AND duration <= 3660", name="ck_task_duration"),
    )
    op.create_table(
        "task_dependencies",
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("work_tasks.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "prerequisite_id",
            sa.String(36),
            sa.ForeignKey("work_tasks.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.CheckConstraint("task_id <> prerequisite_id", name="ck_dependency_not_self"),
    )
    op.create_table(
        "task_schedule_previews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("project_version", sa.Integer(), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_task_schedule_previews_project_id", "task_schedule_previews", ["project_id"]
    )
    op.create_table(
        "task_schedule_changes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "preview_id",
            sa.String(36),
            sa.ForeignKey("task_schedule_previews.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("request_id", sa.String(36), nullable=False, unique=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("actor_name", sa.String(150), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("before", sa.Text(), nullable=False),
        sa.Column("after", sa.Text(), nullable=False),
        sa.Column("schedule_version", sa.Integer(), nullable=False),
        sa.Column("project_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_task_schedule_changes_project_id", "task_schedule_changes", ["project_id"])


def downgrade():
    connection = op.get_bind()
    tables = (
        "task_schedule_changes",
        "task_schedule_previews",
        "task_dependencies",
        "task_schedules",
    )
    if any(connection.scalar(sa.text("SELECT count(*) FROM " + table)) for table in tables):
        raise RuntimeError("Retained scheduling evidence prevents downgrade")
    for table in tables:
        op.drop_table(table)
