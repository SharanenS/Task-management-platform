"""Private test-fixture command, executed only inside the verified people container.

The caller first verifies its disposable Keycloak identity against its run receipt.
No public provisioning API is introduced by S2.
"""

import json
import os
import sys
from uuid import UUID, uuid5

from people.models import (
    Account,
    AccountAudit,
    AccountProvisioning,
    CompanyRoleGrant,
    EmployeeProfile,
)
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

ISSUER = "http://127.0.0.1:8180/realms/taskspace-portals"


def main():
    value = json.load(sys.stdin)
    run_id = str(UUID(value["runId"]))
    subject = str(UUID(value["subject"]))
    if value["username"] != "s1-" + run_id:
        raise ValueError("Fixture identity ownership mismatch")
    action = value["action"]
    if action not in {
        "create",
        "managed_inspect",
        "managed_cleanup",
        "cleanup",
        "account_active",
        "profile_active",
        "profile_missing",
        "profile_restore",
        "role",
    }:
        raise ValueError("Invalid fixture operation")
    profile_id = str(uuid5(UUID(run_id), "employee-profile"))
    engine = create_engine(os.environ["PEOPLE_DATABASE_URL"], hide_parameters=True)
    with Session(engine) as session, session.begin():
        account = session.get(Account, run_id)
        if action == "create":
            if account or session.scalar(
                select(Account).where(Account.issuer == ISSUER, Account.subject == subject)
            ):
                raise ValueError("Fixture would overwrite an existing account")
            account = Account(id=run_id, issuer=ISSUER, subject=subject, active=True)
            account.profile = EmployeeProfile(
                id=profile_id, display_name="Acceptance Account", active=True
            )
            account.grants = [CompanyRoleGrant(role="EMPLOYEE")]
            session.add(account)
        else:
            if account is None:
                if action != "cleanup":
                    raise ValueError("Owned fixture account is absent")
                if session.get(EmployeeProfile, profile_id) or session.scalar(
                    select(CompanyRoleGrant).where(CompanyRoleGrant.account_id == run_id)
                ):
                    raise ValueError("Fixture cleanup is incomplete")
                print(json.dumps({"cleaned": True}))
                return
            if (
                account.issuer != ISSUER
                or account.subject != subject
                or (
                    account.profile
                    and (
                        account.profile.id != profile_id
                        or account.profile.display_name != "Acceptance Account"
                    )
                )
                or any(g.role not in {"ADMIN", "MANAGER", "EMPLOYEE", "HR"} for g in account.grants)
            ):
                raise ValueError("Fixture account ownership mismatch")
            if action in {"managed_inspect", "managed_cleanup"}:
                operation_id = str(UUID(value["value"]))
                operation = session.get(AccountProvisioning, operation_id)
                if not operation:
                    print(json.dumps({"absent": True}))
                    return
                creation = session.scalar(
                    select(AccountAudit).where(AccountAudit.request_id == operation.id)
                )
                if (
                    operation.username != "s4-" + run_id
                    or operation.email != "s4-" + run_id + "@example.invalid"
                    or operation.issuer != ISSUER
                    or not creation
                    or creation.actor_id != run_id
                    or creation.action != "CREATE"
                ):
                    raise ValueError("Managed fixture ownership mismatch")
                target = (
                    session.get(Account, operation.account_id) if operation.account_id else None
                )
                if target and (
                    target.subject != operation.subject
                    or target.profile.display_name != "Managed Acceptance"
                ):
                    raise ValueError("Managed fixture association mismatch")
                result = {
                    "subject": operation.subject,
                    "operationId": operation.id,
                    "accountId": operation.account_id,
                    "state": operation.state,
                }
                if action == "managed_cleanup":
                    records = (
                        session.scalars(
                            select(AccountAudit).where(
                                (AccountAudit.operation_id == operation.id)
                                | (AccountAudit.target_id == operation.account_id)
                            )
                        ).all()
                        if operation.account_id
                        else session.scalars(
                            select(AccountAudit).where(AccountAudit.operation_id == operation.id)
                        ).all()
                    )
                    if any(
                        r.actor_id != run_id or r.target_id not in {None, operation.account_id}
                        for r in records
                    ):
                        raise ValueError("Managed fixture change ownership mismatch")
                    for row in records:
                        session.delete(row)
                    session.flush()
                    session.delete(operation)
                    session.flush()
                    if target:
                        session.execute(
                            delete(CompanyRoleGrant).where(CompanyRoleGrant.account_id == target.id)
                        )
                        session.execute(
                            delete(EmployeeProfile).where(EmployeeProfile.account_id == target.id)
                        )
                        session.execute(delete(Account).where(Account.id == target.id))
                    session.flush()
                    session.expire_all()
                    if (
                        session.get(AccountProvisioning, operation_id)
                        or target
                        and session.get(Account, target.id)
                    ):
                        raise ValueError("Managed fixture cleanup incomplete")
                    result["cleaned"] = True
                print(json.dumps(result))
                return
            if action == "cleanup":
                session.execute(
                    delete(CompanyRoleGrant).where(CompanyRoleGrant.account_id == run_id)
                )
                session.execute(delete(EmployeeProfile).where(EmployeeProfile.account_id == run_id))
                session.execute(delete(Account).where(Account.id == run_id))
            elif action in {"account_active", "profile_active"}:
                if not isinstance(value.get("value"), bool):
                    raise ValueError("Invalid fixture state")
                target = account if action == "account_active" else account.profile
                if target is None:
                    raise ValueError("Fixture profile missing")
                target.active = value["value"]
            elif action == "profile_missing":
                session.execute(delete(EmployeeProfile).where(EmployeeProfile.id == profile_id))
            elif action == "profile_restore":
                if account.profile:
                    raise ValueError("Fixture would overwrite a profile")
                session.add(
                    EmployeeProfile(
                        id=profile_id,
                        account_id=run_id,
                        display_name="Acceptance Account",
                        active=True,
                    )
                )
            elif action == "role":
                role = value.get("value")
                if role is not None and role not in {"ADMIN", "MANAGER", "EMPLOYEE", "HR"}:
                    raise ValueError("Invalid company role")
                session.execute(
                    delete(CompanyRoleGrant).where(CompanyRoleGrant.account_id == run_id)
                )
                if role:
                    session.add(CompanyRoleGrant(account_id=run_id, role=role))
    if action == "cleanup":
        with Session(engine) as session:
            if (
                session.get(Account, run_id)
                or session.get(EmployeeProfile, profile_id)
                or session.scalar(
                    select(CompanyRoleGrant).where(CompanyRoleGrant.account_id == run_id)
                )
            ):
                raise ValueError("Fixture cleanup verification failed")
    engine.dispose()
    print(json.dumps({"cleaned": action == "cleanup", "verified": True}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Scoped account fixture operation failed", file=sys.stderr)
        sys.exit(1)
