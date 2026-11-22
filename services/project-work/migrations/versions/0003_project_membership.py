"""Explicit project appointments and retained membership history."""

import sqlalchemy as sa
from alembic import op

revision = "0003_project_membership"
down_revision = "0002_manager_projects"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "project_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("display_name", sa.String(150), nullable=False),
        sa.Column("responsibility", sa.String(20), nullable=False),
        sa.Column("duties", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "account_id", name="uq_project_member_account"),
        sa.CheckConstraint(
            "responsibility IN ('CONTRIBUTOR', 'LEADER')", name="ck_project_responsibility"
        ),
    )
    op.create_index(
        "uq_project_active_leader",
        "project_members",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("active AND responsibility = 'LEADER'"),
        sqlite_where=sa.text("active AND responsibility = 'LEADER'"),
    )
    op.create_table(
        "project_membership_changes",
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
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("before", sa.Text(), nullable=False),
        sa.Column("after", sa.Text(), nullable=False),
        sa.Column("project_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    if op.get_bind().scalar(
        sa.text("SELECT count(*) FROM project_membership_changes")
    ) or op.get_bind().scalar(sa.text("SELECT count(*) FROM project_members")):
        raise RuntimeError("Preserve membership history before downgrading")
    op.drop_table("project_membership_changes")
    op.drop_index("uq_project_active_leader", table_name="project_members")
    op.drop_table("project_members")
