"""Create workflow rules, source-event inbox, and executions.

Revision ID: 20261028_01
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261028_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    trigger = sa.Enum("TASK_COMPLETED", name="workflow_trigger_type")
    action = sa.Enum("PROJECT_TASK_EXPORT", name="workflow_action_type")
    execution = sa.Enum("PENDING", "SUCCEEDED", "FAILED", name="workflow_execution_status")
    inbox = sa.Enum("RECEIVED", "PROCESSED", "QUARANTINED", name="workflow_inbox_status")
    op.create_table(
        "workflow_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("trigger_type", trigger, nullable=False),
        sa.Column("action_type", action, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("creator_employee_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "workflow_source_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("status", inbox, nullable=False),
        sa.Column("failure_classification", sa.String(64)),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "rule_id",
            sa.Uuid(),
            sa.ForeignKey("workflow_rules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_event_id",
            sa.Uuid(),
            sa.ForeignKey("workflow_source_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("status", execution, nullable=False),
        sa.Column("resulting_job_id", sa.Uuid()),
        sa.Column("failure_classification", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("rule_id", "source_event_id"),
    )
    for table, names in {
        "workflow_rules": ("project_id", "enabled", "creator_employee_id", "created_at"),
        "workflow_source_events": ("project_id", "task_id"),
        "workflow_executions": (
            "rule_id",
            "source_event_id",
            "project_id",
            "task_id",
            "status",
            "created_at",
        ),
    }.items():
        for name in names:
            op.create_index(f"ix_{table}_{name}", table, [name])


def downgrade() -> None:
    raise RuntimeError("Forward-only migrations are required")
