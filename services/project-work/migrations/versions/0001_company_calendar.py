"""Immutable calendar publication with owned server-issued previews."""

import sqlalchemy as sa
from alembic import op

revision = "0001_company_calendar"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "calendar_previews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("base_version_id", sa.String(36), nullable=True),
        sa.Column("config", sa.Text(), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("tzdb_version", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "calendar_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column(
            "preview_id",
            sa.String(36),
            sa.ForeignKey("calendar_previews.id", ondelete="RESTRICT"),
            unique=True,
            nullable=False,
        ),
        sa.Column("request_id", sa.String(36), unique=True, nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("config", sa.Text(), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("tzdb_version", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("issuer", "number", name="uq_calendar_number"),
    )
    with op.batch_alter_table("calendar_previews") as batch:
        batch.create_foreign_key(
            "fk_calendar_preview_base",
            "calendar_versions",
            ["base_version_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM calendar_versions")):
        raise RuntimeError("Preserve published calendar history before downgrading")
    with op.batch_alter_table("calendar_previews") as batch:
        batch.drop_constraint("fk_calendar_preview_base", type_="foreignkey")
    op.drop_table("calendar_versions")
    op.drop_table("calendar_previews")
