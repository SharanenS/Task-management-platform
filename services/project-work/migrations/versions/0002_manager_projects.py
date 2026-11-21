"""Initial project ownership and confirmed immutable deadline commitment."""

import sqlalchemy as sa
from alembic import op

revision = "0002_manager_projects"
down_revision = "0001_company_calendar"
branch_labels = None
depends_on = None


def deadline_fields():
    return [
        sa.Column("deadline_date", sa.String(10), nullable=False),
        sa.Column("approved_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_local", sa.String(50), nullable=False),
        sa.Column(
            "calendar_version_id",
            sa.String(36),
            sa.ForeignKey("calendar_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("calendar_number", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(100), nullable=False),
        sa.Column("tzdb_version", sa.String(30), nullable=False),
    ]


def upgrade():
    op.create_table(
        "project_previews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("actor_name", sa.String(150), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("objectives", sa.Text(), nullable=False),
        *deadline_fields(),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("request_id", sa.String(36), unique=True, nullable=False),
        sa.Column(
            "preview_id",
            sa.String(36),
            sa.ForeignKey("project_previews.id", ondelete="RESTRICT"),
            unique=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("objectives", sa.Text(), nullable=False),
        sa.Column("creator_id", sa.String(36), nullable=False),
        sa.Column("creator_name", sa.String(150), nullable=False),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("owner_name", sa.String(150), nullable=False),
        *deadline_fields(),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM projects")):
        raise RuntimeError("Preserve project commitments before downgrading")
    op.drop_table("projects")
    op.drop_table("project_previews")
