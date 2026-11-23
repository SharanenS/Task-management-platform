"""Owner-scoped coordination with retained recipients and follow-up history."""

import sqlalchemy as sa
from alembic import op

revision = "0004_manager_coordination"
down_revision = "0003_project_membership"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "coordination_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(36), nullable=False, unique=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("topic", sa.String(150), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.String(300), nullable=False),
        sa.Column("acknowledgement_required", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('UPDATE', 'MEETING', 'CHECK_IN')", name="ck_coordination_kind"
        ),
    )
    op.create_index("ix_coordination_records_project_id", "coordination_records", ["project_id"])
    op.create_table(
        "coordination_recipients",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "record_id",
            sa.String(36),
            sa.ForeignKey("coordination_records.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("display_name", sa.String(150), nullable=False),
        sa.UniqueConstraint("record_id", "account_id", name="uq_coordination_recipient"),
    )
    op.create_table(
        "coordination_follow_ups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "record_id",
            sa.String(36),
            sa.ForeignKey("coordination_records.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(36), nullable=False, unique=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("next_follow_up_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    if any(
        op.get_bind().scalar(sa.text("SELECT count(*) FROM " + table))
        for table in ("coordination_records", "coordination_recipients", "coordination_follow_ups")
    ):
        raise RuntimeError("Preserve coordination history before downgrading")
    op.drop_table("coordination_follow_ups")
    op.drop_table("coordination_recipients")
    op.drop_index("ix_coordination_records_project_id", table_name="coordination_records")
    op.drop_table("coordination_records")
