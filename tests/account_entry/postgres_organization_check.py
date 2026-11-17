"""Verify reporting races in PostgreSQL with explicitly owned synthetic records."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from people.management import ManagementError
from people.models import Account, CompanyRoleGrant, EmployeeProfile, OrganizationAudit
from people.organization import OrganizationManagement
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker
from taskspace_security.tokens import Identity


def main():
    engine = create_engine(os.environ["PEOPLE_DATABASE_URL"], hide_parameters=True)
    if engine.url.host != "people-db" or engine.url.database != "taskspace_people":
        raise ValueError("Wrong probe boundary")
    sessions = sessionmaker(engine)
    issuer = "https://organization-race.invalid/" + str(uuid4())
    account_id, subject, admin_profile, first, second = [str(uuid4()) for _ in range(5)]
    profile_ids = [admin_profile, first, second]
    try:
        with sessions() as s:
            account = Account(id=account_id, issuer=issuer, subject=subject, active=True)
            account.profile = EmployeeProfile(
                id=admin_profile, issuer=issuer, display_name="Owned administrator", active=True
            )
            account.grants = [CompanyRoleGrant(role="ADMIN")]
            s.add(account)
            for index, profile in enumerate([first, second]):
                s.add(
                    EmployeeProfile(
                        id=profile,
                        issuer=issuer,
                        display_name="Owned report " + str(index),
                        active=True,
                    )
                )
            s.commit()
        barrier = Barrier(2)
        service = OrganizationManagement(sessions, None)

        def update(index):
            barrier.wait(timeout=5)
            try:
                return service.change(
                    Identity(issuer, subject),
                    {
                        "request_id": str(uuid4()),
                        "action": "EMPLOYEE_UPDATE",
                        "entity_id": [first, second][index],
                        "version": 1,
                        "name": "Owned report " + str(index),
                        "manager_id": [second, first][index],
                    },
                )["state"]
            except ManagementError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(update, [0, 1]))
        assert sorted(results) == ["COMPLETE", "reporting_cycle"]
        with sessions() as s:
            rows = [s.get(EmployeeProfile, first), s.get(EmployeeProfile, second)]
            assert sum(r.manager_id is not None for r in rows) == 1
            assert sum(r.version for r in rows) == 3
            assert s.get(Account, account_id).grants[0].role == "ADMIN"
    finally:
        with sessions() as s:
            rows = s.scalars(
                select(EmployeeProfile).where(EmployeeProfile.id.in_(profile_ids))
            ).all()
            assert all(
                r.issuer == issuer
                and r.display_name.startswith("Owned ")
                and r.account_id in {None, account_id}
                for r in rows
            )
            account = s.get(Account, account_id)
            assert not account or account.issuer == issuer and account.subject == subject
            audit = s.scalars(
                select(OrganizationAudit).where(OrganizationAudit.issuer == issuer)
            ).all()
            assert all(r.actor_id == account_id and r.entity_id in {first, second} for r in audit)
            for row in rows:
                row.manager_id = None
            s.flush()
            s.execute(delete(OrganizationAudit).where(OrganizationAudit.issuer == issuer))
            s.execute(delete(EmployeeProfile).where(EmployeeProfile.id.in_(profile_ids)))
            s.execute(delete(CompanyRoleGrant).where(CompanyRoleGrant.account_id == account_id))
            s.execute(delete(Account).where(Account.id == account_id))
            s.commit()
        with sessions() as s:
            assert not s.scalar(
                select(EmployeeProfile.id).where(EmployeeProfile.id.in_(profile_ids))
            )
            assert not s.get(Account, account_id)
            assert not s.scalar(
                select(OrganizationAudit.id).where(OrganizationAudit.issuer == issuer)
            )
        engine.dispose()
    print("Concurrent reporting cycle rejected; exact owned records and audits removed.")


if __name__ == "__main__":
    main()
