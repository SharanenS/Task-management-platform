"""Shared company structure and optional employment/account associations."""

import sqlalchemy as sa
from alembic import op

revision = "0004_company_structure"
down_revision = "0003_account_management"
branch_labels = None
depends_on = None


def upgrade():
    for table, constraint in (
        ("departments", "uq_department_name"),
        ("job_titles", "uq_job_title_name"),
    ):
        op.create_table(
            table,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("issuer", sa.String(512), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("normalized_name", sa.String(200), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.UniqueConstraint("issuer", "normalized_name", name=constraint),
        )
    op.add_column("employee_profiles", sa.Column("issuer", sa.String(512), nullable=True))
    op.execute(
        sa.text(
            "UPDATE employee_profiles SET issuer=(SELECT issuer FROM accounts "
            "WHERE accounts.id=employee_profiles.account_id)"
        )
    )
    with op.batch_alter_table("employee_profiles") as batch:
        batch.alter_column("issuer", existing_type=sa.String(512), nullable=False)
        batch.alter_column("account_id", existing_type=sa.String(36), nullable=True)
        batch.add_column(sa.Column("department_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("job_title_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("manager_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch.create_foreign_key(
            "fk_employee_department", "departments", ["department_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_foreign_key(
            "fk_employee_job_title", "job_titles", ["job_title_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_foreign_key(
            "fk_employee_manager", "employee_profiles", ["manager_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_check_constraint(
            "ck_employee_not_self_manager", "manager_id IS NULL OR manager_id <> id"
        )
    with op.batch_alter_table("account_provisioning") as batch:
        batch.add_column(sa.Column("employee_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_provisioning_employee",
            "employee_profiles",
            ["employee_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_unique_constraint("uq_provisioning_employee", ["employee_id"])
    op.create_table(
        "organization_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False, unique=True),
        sa.Column(
            "actor_id",
            sa.String(36),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("entity_kind", sa.String(20), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("intent_hash", sa.String(64), nullable=False),
        sa.Column("before", sa.Text(), nullable=False),
        sa.Column("after", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    if op.get_bind().scalar(
        sa.text("SELECT count(*) FROM employee_profiles WHERE account_id IS NULL")
    ):
        raise RuntimeError("Preserve unlinked employee records before downgrading")
    op.drop_table("organization_audit")
    with op.batch_alter_table("account_provisioning") as batch:
        batch.drop_constraint("fk_provisioning_employee", type_="foreignkey")
        batch.drop_constraint("uq_provisioning_employee", type_="unique")
        batch.drop_column("employee_id")
    with op.batch_alter_table("employee_profiles") as batch:
        for name in ("fk_employee_department", "fk_employee_job_title", "fk_employee_manager"):
            batch.drop_constraint(name, type_="foreignkey")
        batch.drop_constraint("ck_employee_not_self_manager", type_="check")
        for name in ("department_id", "job_title_id", "manager_id", "version", "issuer"):
            batch.drop_column(name)
        batch.alter_column("account_id", existing_type=sa.String(36), nullable=False)
    op.drop_table("job_titles")
    op.drop_table("departments")
