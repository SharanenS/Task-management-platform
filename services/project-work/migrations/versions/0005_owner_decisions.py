"""Separate owner decisions and forecast inputs from original project commitments."""

import sqlalchemy as sa
from alembic import op

revision = "0005_owner_decisions"
down_revision = "0004_manager_coordination"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "project_delivery_state",
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("schedule_version", sa.Integer(), nullable=False),
    )
    op.create_table(
        "project_delivery_assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("schedule_version", sa.Integer(), nullable=False),
        sa.Column("project_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("forecast_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('ASSESSED', 'UNASSESSED')", name="ck_delivery_assessment_status"
        ),
        sa.CheckConstraint(
            "(status = 'ASSESSED' AND forecast_at IS NOT NULL) OR "
            "(status = 'UNASSESSED' AND forecast_at IS NULL)",
            name="ck_delivery_forecast_presence",
        ),
    )
    op.create_index(
        "ix_project_delivery_assessments_project_id", "project_delivery_assessments", ["project_id"]
    )
    op.create_table(
        "project_owner_escalations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_request_id", sa.String(36), nullable=False),
        sa.Column(
            "assessment_id",
            sa.String(36),
            sa.ForeignKey("project_delivery_assessments.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("affected_team", sa.String(300), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_request_id"),
        sa.CheckConstraint("status IN ('PENDING', 'DECIDED')", name="ck_owner_escalation_status"),
    )
    op.create_index(
        "ix_project_owner_escalations_project_id", "project_owner_escalations", ["project_id"]
    )
    op.create_table(
        "project_owner_decision_previews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "escalation_id",
            sa.String(36),
            sa.ForeignKey("project_owner_escalations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("project_version", sa.Integer(), nullable=False),
        sa.Column("escalation_version", sa.Integer(), nullable=False),
        sa.Column(
            "assessment_id",
            sa.String(36),
            sa.ForeignKey("project_delivery_assessments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "calendar_version_id",
            sa.String(36),
            sa.ForeignKey("calendar_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("deadline_date", sa.String(10), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_local", sa.String(50), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "project_owner_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "escalation_id",
            sa.String(36),
            sa.ForeignKey("project_owner_escalations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "assessment_id",
            sa.String(36),
            sa.ForeignKey("project_delivery_assessments.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "preview_id",
            sa.String(36),
            sa.ForeignKey("project_owner_decision_previews.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("actor_name", sa.String(150), nullable=False),
        sa.Column("actor_role", sa.String(20), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("affected_team", sa.String(300), nullable=False),
        sa.Column("previous_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("forecast_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assessment_state", sa.String(20), nullable=False),
        sa.Column("revised_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("previous_overdue", sa.Boolean(), nullable=False),
        sa.Column("project_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("preview_id"),
        sa.UniqueConstraint("request_id"),
        sa.UniqueConstraint("escalation_id"),
        sa.CheckConstraint(
            "outcome IN ('REVISE_DEADLINE', 'ACCEPT_FORECAST_LATE', 'REQUEST_REPLAN')",
            name="ck_owner_decision_outcome",
        ),
    )
    op.create_index(
        "ix_project_owner_decisions_project_id", "project_owner_decisions", ["project_id"]
    )

    op.create_table(
        "project_review_fallbacks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("actor_name", sa.String(150), nullable=False),
        sa.Column("leader_id", sa.String(36), nullable=True),
        sa.Column("leader_name", sa.String(150), nullable=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(36), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column("revocation_request_id", sa.String(36), nullable=True),
        sa.Column("revocation_hash", sa.String(64), nullable=True),
        sa.UniqueConstraint("request_id"),
        sa.UniqueConstraint("revocation_request_id"),
        sa.CheckConstraint(
            "scope IN ('REVIEWS', 'EXTENSIONS', 'BOTH')", name="ck_review_fallback_scope"
        ),
    )
    op.create_index(
        "ix_project_review_fallbacks_project_id", "project_review_fallbacks", ["project_id"]
    )


def downgrade():
    if any(
        op.get_bind().scalar(sa.text("SELECT count(*) FROM " + table))
        for table in (
            "project_review_fallbacks",
            "project_delivery_state",
            "project_delivery_assessments",
            "project_owner_escalations",
            "project_owner_decision_previews",
            "project_owner_decisions",
        )
    ):
        raise RuntimeError("Preserve owner decisions and assessment history before downgrading")
    op.drop_index("ix_project_review_fallbacks_project_id", table_name="project_review_fallbacks")
    op.drop_table("project_review_fallbacks")
    op.drop_index("ix_project_owner_decisions_project_id", table_name="project_owner_decisions")
    op.drop_table("project_owner_decisions")
    op.drop_table("project_owner_decision_previews")
    op.drop_index("ix_project_owner_escalations_project_id", table_name="project_owner_escalations")
    op.drop_table("project_owner_escalations")
    op.drop_index(
        "ix_project_delivery_assessments_project_id", table_name="project_delivery_assessments"
    )
    op.drop_table("project_delivery_assessments")
    op.drop_table("project_delivery_state")
