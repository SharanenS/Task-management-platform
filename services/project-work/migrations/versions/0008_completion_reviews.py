"""Retain task execution, versioned completion submissions and audited review decisions."""

import sqlalchemy as sa
from alembic import op

revision = "0008_completion_reviews"
down_revision = "0007_task_scheduling"
branch_labels = depends_on = None


def fk(name, target, primary=False, unique=False):
    return sa.Column(
        name,
        sa.String(36),
        sa.ForeignKey(target, ondelete="RESTRICT"),
        nullable=False,
        primary_key=primary,
        unique=unique,
    )


def upgrade():
    op.create_table(
        "task_executions",
        fk("task_id", "work_tasks.id", primary=True),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("blocker", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name="ck_execution_progress"),
    )
    op.create_table(
        "task_submissions",
        sa.Column("id", sa.String(36), primary_key=True),
        fk("task_id", "work_tasks.id"),
        fk("assignment_id", "task_assignments.id"),
        fk("request_id", "task_changes.request_id", unique=True),
        sa.Column("submitter_id", sa.String(36), nullable=False),
        sa.Column("submitter_name", sa.String(150), nullable=False),
        sa.Column("task_version", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("snapshot", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("task_id", "task_version", name="uq_submission_task_version"),
    )
    op.create_index("ix_task_submissions_task_id", "task_submissions", ["task_id"])
    op.create_index(
        "uq_open_task_submission",
        "task_submissions",
        ["task_id"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
        sqlite_where=sa.text("closed_at IS NULL"),
    )
    op.create_table(
        "task_review_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        fk("submission_id", "task_submissions.id", unique=True),
        fk("request_id", "task_changes.request_id", unique=True),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("actor_name", sa.String(150), nullable=False),
        sa.Column("outcome", sa.String(12), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("self_approval", sa.Boolean(), nullable=False),
        sa.Column(
            "fallback_id",
            sa.String(36),
            sa.ForeignKey("project_review_fallbacks.id", ondelete="RESTRICT"),
        ),
        sa.Column("task_version", sa.Integer(), nullable=False),
        sa.Column("project_version", sa.Integer(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("outcome IN ('APPROVE','RETURN')", name="ck_review_outcome"),
        sa.CheckConstraint(
            "NOT self_approval OR outcome = 'APPROVE'", name="ck_review_self_approval"
        ),
    )


def downgrade():
    connection = op.get_bind()
    tables = ("task_review_decisions", "task_submissions", "task_executions")
    if any(connection.scalar(sa.text("SELECT count(*) FROM " + table)) for table in tables):
        raise RuntimeError("Retained completion evidence prevents downgrade")
    for table in tables:
        op.drop_table(table)
