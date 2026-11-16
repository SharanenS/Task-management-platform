"""Verify the migrated people schema and rollback-owned probes in PostgreSQL only."""

import os
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from people.models import Account, Base, CompanyRoleGrant, EmployeeProfile
from sqlalchemy import create_engine, insert, select
from sqlalchemy.exc import IntegrityError


def main():
    engine = create_engine(os.environ["PEOPLE_DATABASE_URL"], hide_parameters=True)
    if engine.url.database != "taskspace_people" or engine.url.host != "people-db":
        raise ValueError("Wrong integration database boundary")
    account_id, profile_id, subject, second_account = (str(uuid4()) for _ in range(4))
    with engine.connect() as connection:
        if compare_metadata(MigrationContext.configure(connection), Base.metadata):
            raise ValueError("Migration differs from models")
        connection.rollback()
        transaction = connection.begin()
        try:
            connection.execute(
                insert(Account).values(
                    id=account_id,
                    issuer="https://integration.invalid",
                    subject=subject,
                    active=True,
                )
            )
            connection.execute(
                insert(EmployeeProfile).values(
                    id=profile_id,
                    account_id=account_id,
                    display_name="Scoped integration probe",
                    active=True,
                )
            )
            connection.execute(
                insert(CompanyRoleGrant).values(account_id=account_id, role="EMPLOYEE")
            )
            connection.execute(
                insert(Account).values(
                    id=second_account,
                    issuer="https://integration.invalid",
                    subject=str(uuid4()),
                    active=True,
                )
            )
            probes = [
                insert(Account).values(
                    id=str(uuid4()),
                    issuer="https://integration.invalid",
                    subject=subject,
                    active=True,
                ),
                insert(CompanyRoleGrant).values(account_id=account_id, role="ADMIN"),
                insert(CompanyRoleGrant).values(account_id=str(uuid4()), role="EMPLOYEE"),
                insert(CompanyRoleGrant).values(account_id=second_account, role="TEAM_LEADER"),
            ]
            names = [
                "uq_account_identity",
                "uq_account_company_role",
                "company_role_grants_account_id_fkey",
                "ck_company_role",
            ]
            for statement, expected in zip(probes, names, strict=True):
                nested = connection.begin_nested()
                try:
                    connection.execute(statement)
                except IntegrityError as error:
                    nested.rollback()
                    if error.orig.diag.constraint_name != expected:
                        raise ValueError("PostgreSQL constraint mismatch") from None
                    print("postgres_probe:" + expected, flush=True)
                else:
                    nested.rollback()
                    raise ValueError("A required PostgreSQL constraint was absent")
        finally:
            transaction.rollback()
        for model, key in (
            (Account, account_id),
            (Account, second_account),
            (EmployeeProfile, profile_id),
        ):
            if connection.execute(select(model.id).where(model.id == key)).first():
                raise ValueError("Integration rollback failed")
        if connection.execute(
            select(CompanyRoleGrant.account_id).where(CompanyRoleGrant.account_id == account_id)
        ).first():
            raise ValueError("Integration role rollback failed")
    engine.dispose()
    print(
        "PostgreSQL schema/identity/role/foreign-key constraints and exact probe rollback verified."
    )


if __name__ == "__main__":
    main()
