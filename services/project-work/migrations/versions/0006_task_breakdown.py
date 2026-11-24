"""Project tasks and retained single-assignee planning history."""

import sqlalchemy as sa
from alembic import op

revision = "0006_task_breakdown"
down_revision = "0005_owner_decisions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "work_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("acceptance_criteria", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("creator_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_task_version"),
        sa.CheckConstraint(
            "status IN ('PENDING','IN_PROGRESS','AWAITING_REVIEW','COMPLETED','CANCELLED')",
            name="ck_task_status",
        ),
    )
    op.create_index("ix_work_tasks_project_id", "work_tasks", ["project_id"])
    op.create_table(
        "task_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("work_tasks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("display_name", sa.String(150), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_task_assignments_task_id", "task_assignments", ["task_id"])
    op.create_index(
        "uq_task_active_assignment",
        "task_assignments",
        ["task_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
        sqlite_where=sa.text("ended_at IS NULL"),
    )
    op.create_table(
        "task_changes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("work_tasks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(36), nullable=False, unique=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("actor_name", sa.String(150), nullable=False),
        sa.Column("action", sa.String(12), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("before", sa.Text(), nullable=False),
        sa.Column("after", sa.Text(), nullable=False),
        sa.Column("task_version", sa.Integer(), nullable=False),
        sa.Column("project_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "task_version", name="uq_task_change_version"),
    )
    op.create_index("ix_task_changes_task_id", "task_changes", ["task_id"])


def downgrade():
    connection = op.get_bind()
    for table in ("task_changes", "task_assignments", "work_tasks"):
        if connection.scalar(sa.text("SELECT count(*) FROM " + table)):
            raise RuntimeError("Retained task history prevents downgrade")
    for table in ("task_changes", "task_assignments", "work_tasks"):
        op.drop_table(table)
