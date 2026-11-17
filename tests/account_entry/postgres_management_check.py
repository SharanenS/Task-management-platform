"""Real PostgreSQL race probe; only UUID-owned synthetic identities are touched."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from people.access import AccessDenied
from people.management import AccountManagement
from people.models import Account, AccountAudit, CompanyRoleGrant, EmployeeProfile
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker
from taskspace_security.tokens import Identity


def main():
    engine = create_engine(os.environ["PEOPLE_DATABASE_URL"], hide_parameters=True)
    if engine.url.host != "people-db" or engine.url.database != "taskspace_people":
        raise ValueError("Wrong probe boundary")
    sessions = sessionmaker(engine)
    issuer = "https://concurrency.invalid/" + str(uuid4())
    accounts = [str(uuid4()), str(uuid4())]
    subjects = [str(uuid4()), str(uuid4())]
    profiles = [str(uuid4()), str(uuid4())]
    try:
        with sessions() as s:
            for i in range(2):
                account = Account(id=accounts[i], issuer=issuer, subject=subjects[i], active=True)
                account.profile = EmployeeProfile(
                    id=profiles[i],
                    issuer=issuer,
                    display_name="Owned concurrency probe",
                    active=True,
                )
                account.grants = [CompanyRoleGrant(role="ADMIN")]
                s.add(account)
            s.commit()
        barrier = Barrier(2)
        service = AccountManagement(sessions, None)

        def demote(index):
            barrier.wait(timeout=5)
            try:
                result = service.change(
                    Identity(issuer, subjects[index]),
                    {
                        "request_id": str(uuid4()),
                        "account_id": accounts[1 - index],
                        "action": "ROLE",
                        "role": "EMPLOYEE",
                        "version": 1,
                    },
                )
                return result["state"]
            except AccessDenied:
                return "DENIED"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(demote, [0, 1]))
        assert sorted(results) == ["COMPLETE", "DENIED"]
        with sessions() as s:
            grants = s.scalars(
                select(CompanyRoleGrant).where(CompanyRoleGrant.account_id.in_(accounts))
            ).all()
            assert sorted(g.role for g in grants) == ["ADMIN", "EMPLOYEE"]
            history = s.scalars(
                select(AccountAudit).where(AccountAudit.actor_id.in_(accounts))
            ).all()
            assert (
                len(history) == 1
                and history[0].state == "COMPLETE"
                and history[0].target_id in accounts
            )
        print(
            "Concurrent cross-demotions serialized; one active administrator retained; "
            "stale actor denied."
        )
    finally:
        with sessions() as s:
            owned = s.scalars(select(Account).where(Account.id.in_(accounts))).all()
            assert all(
                a.issuer == issuer and a.subject in subjects and a.profile.id in profiles
                for a in owned
            )
            rows = s.scalars(select(AccountAudit).where(AccountAudit.actor_id.in_(accounts))).all()
            assert all(r.target_id in accounts for r in rows)
            s.execute(delete(AccountAudit).where(AccountAudit.actor_id.in_(accounts)))
            s.execute(delete(CompanyRoleGrant).where(CompanyRoleGrant.account_id.in_(accounts)))
            s.execute(delete(EmployeeProfile).where(EmployeeProfile.account_id.in_(accounts)))
            s.execute(delete(Account).where(Account.id.in_(accounts)))
            s.commit()
        with sessions() as s:
            assert not s.scalars(select(Account).where(Account.id.in_(accounts))).all()
            assert not s.scalars(
                select(EmployeeProfile).where(EmployeeProfile.id.in_(profiles))
            ).all()
            assert not s.scalars(
                select(AccountAudit).where(AccountAudit.actor_id.in_(accounts))
            ).all()
        engine.dispose()
        print(
            "Exact concurrency probe accounts, profiles, roles and audit records verified absent."
        )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Scoped PostgreSQL account-management verification failed; private details omitted."
        ) from None
