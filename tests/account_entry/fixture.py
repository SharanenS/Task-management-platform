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
    Department,
    EmployeeProfile,
    JobTitle,
    OrganizationAudit,
)
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

ISSUER = "http://127.0.0.1:8180/realms/taskspace-portals"


def task_peer_account(session, run_id, subject, action):
    run_id, subject = str(UUID(run_id)), str(UUID(subject))
    peer_id = str(uuid5(UUID(run_id), "task-peer-account"))
    profile_id = str(uuid5(UUID(run_id), "task-peer-profile"))
    peer = session.get(Account, peer_id)
    if action == "task_peer_create":
        if (
            peer
            or session.get(EmployeeProfile, profile_id)
            or session.scalar(
                select(Account.id).where(Account.issuer == ISSUER, Account.subject == subject)
            )
        ):
            raise ValueError("Task peer fixture would overwrite existing data")
        peer = Account(id=peer_id, issuer=ISSUER, subject=subject, active=True)
        peer.profile = EmployeeProfile(
            id=profile_id, issuer=ISSUER, display_name="Task acceptance peer", active=True
        )
        peer.grants = [CompanyRoleGrant(role="EMPLOYEE")]
        session.add(peer)
        session.flush()
    if peer and (
        peer.issuer != ISSUER
        or peer.subject != subject
        or not peer.profile
        or peer.profile.id != profile_id
        or peer.profile.display_name != "Task acceptance peer"
        or len(peer.grants) != 1
        or peer.grants[0].role != "EMPLOYEE"
    ):
        raise ValueError("Task peer fixture ownership mismatch")
    if action == "task_peer_cleanup" and peer:
        if session.scalar(
            select(AccountAudit.id).where(
                (AccountAudit.actor_id == peer_id) | (AccountAudit.target_id == peer_id)
            )
        ) or session.scalar(
            select(AccountProvisioning.id).where(AccountProvisioning.account_id == peer_id)
        ):
            raise ValueError("Unexpected task peer account references")
        session.execute(delete(CompanyRoleGrant).where(CompanyRoleGrant.account_id == peer_id))
        session.execute(
            delete(EmployeeProfile).where(
                EmployeeProfile.id == profile_id, EmployeeProfile.account_id == peer_id
            )
        )
        session.execute(delete(Account).where(Account.id == peer_id))
        session.flush()
        session.expire_all()
        peer = session.get(Account, peer_id)
    if peer is None and (
        session.get(EmployeeProfile, profile_id)
        or session.scalar(
            select(CompanyRoleGrant.account_id).where(CompanyRoleGrant.account_id == peer_id)
        )
    ):
        raise ValueError("Task peer cleanup incomplete")
    return {
        "accountId": peer_id,
        "subject": peer.subject if peer else None,
        "absent": peer is None,
        "cleaned": action == "task_peer_cleanup" and peer is None,
    }


def main():
    value = json.load(sys.stdin)
    run_id = str(UUID(value["runId"]))
    subject = str(UUID(value["subject"]))
    if value["username"] != "s1-" + run_id:
        raise ValueError("Fixture identity ownership mismatch")
    action = value["action"]
    if action not in {
        "create",
        "inspect",
        "task_peer_create",
        "task_peer_inspect",
        "task_peer_cleanup",
        "project_other_create",
        "project_other_inspect",
        "project_other_cleanup",
        "project_other_role",
        "project_other_active",
        "organization_inspect",
        "organization_cleanup",
        "organization_account",
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
                id=profile_id, issuer=ISSUER, display_name="Acceptance Account", active=True
            )
            account.grants = [CompanyRoleGrant(role="EMPLOYEE")]
            session.add(account)
        else:
            if account is None:
                if action not in {"cleanup", "inspect"}:
                    raise ValueError("Owned fixture account is absent")
                if session.get(EmployeeProfile, profile_id) or session.scalar(
                    select(CompanyRoleGrant).where(CompanyRoleGrant.account_id == run_id)
                ):
                    raise ValueError("Fixture cleanup is incomplete")
                print(json.dumps({"cleaned": action == "cleanup", "absent": True}))
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
            if action == "inspect":
                print(json.dumps({"absent": False}))
                return
            if action.startswith("task_peer_"):
                result = task_peer_account(session, run_id, value["value"], action)
                print(json.dumps(result))
                return
            if action.startswith("project_other_"):
                other_id = str(uuid5(UUID(run_id), "project-account"))
                other_profile = str(uuid5(UUID(run_id), "project-profile"))
                other = session.get(Account, other_id)
                if action == "project_other_create":
                    other_subject = str(UUID(value["value"]))
                    if other or session.scalar(
                        select(Account).where(
                            Account.issuer == ISSUER, Account.subject == other_subject
                        )
                    ):
                        raise ValueError("Secondary project fixture already exists")
                    other = Account(id=other_id, issuer=ISSUER, subject=other_subject, active=True)
                    other.profile = EmployeeProfile(
                        id=other_profile,
                        issuer=ISSUER,
                        display_name="Project acceptance manager",
                        active=True,
                    )
                    other.grants = [CompanyRoleGrant(role="MANAGER")]
                    session.add(other)
                    session.flush()
                if other and (
                    other.issuer != ISSUER
                    or other.profile.id != other_profile
                    or other.profile.display_name != "Project acceptance manager"
                    or len(other.grants) != 1
                    or other.grants[0].role not in {"MANAGER", "EMPLOYEE", "HR"}
                ):
                    raise ValueError("Secondary project fixture ownership mismatch")
                if action == "project_other_role":
                    if not other or value["value"] not in {"MANAGER", "EMPLOYEE", "HR"}:
                        raise ValueError("Invalid secondary role")
                    other.grants[0].role = value["value"]
                if action == "project_other_active":
                    if not other or value["value"] not in {"true", "false"}:
                        raise ValueError("Invalid secondary active state")
                    other.active = value["value"] == "true"
                result = {"accountId": other_id, "subject": other.subject if other else None}
                if action == "project_other_cleanup":
                    if other:
                        session.execute(
                            delete(CompanyRoleGrant).where(CompanyRoleGrant.account_id == other_id)
                        )
                        session.execute(
                            delete(EmployeeProfile).where(
                                EmployeeProfile.id == other_profile,
                                EmployeeProfile.account_id == other_id,
                            )
                        )
                        session.execute(delete(Account).where(Account.id == other_id))
                        session.flush()
                        session.expire_all()
                    if session.get(Account, other_id) or session.get(
                        EmployeeProfile, other_profile
                    ):
                        raise ValueError("Secondary cleanup incomplete")
                    result["cleaned"] = True
                print(json.dumps(result))
                return
            if action.startswith("organization_"):
                secondary_id = str(uuid5(UUID(run_id), "organization-account"))
                if action == "organization_account":
                    secondary_subject = str(UUID(value["value"]))
                    if session.get(Account, secondary_id) or session.scalar(
                        select(Account).where(
                            Account.issuer == ISSUER, Account.subject == secondary_subject
                        )
                    ):
                        raise ValueError("Secondary fixture already exists")
                    secondary = Account(
                        id=secondary_id, issuer=ISSUER, subject=secondary_subject, active=True
                    )
                    secondary.grants = [CompanyRoleGrant(role="EMPLOYEE")]
                    session.add(secondary)
                    print(json.dumps({"accountId": secondary_id}))
                    return
                records = session.scalars(
                    select(OrganizationAudit).where(OrganizationAudit.actor_id == run_id)
                ).all()
                ids = {r.entity_id for r in records}
                groups = {Department: [], JobTitle: [], EmployeeProfile: []}
                for model in groups:
                    groups[model] = session.scalars(select(model).where(model.id.in_(ids))).all()
                    for row in groups[model]:
                        name = row.display_name if model is EmployeeProfile else row.name
                        if row.issuer != ISSUER or run_id not in name:
                            raise ValueError("Organization resource ownership mismatch")
                employees = groups[EmployeeProfile]
                employee_ids = {r.id for r in employees}
                if any(
                    r.account_id not in {None, secondary_id}
                    or r.manager_id not in {None, *employee_ids}
                    for r in employees
                ):
                    raise ValueError("Organization association ownership mismatch")
                if session.scalar(
                    select(OrganizationAudit.id).where(
                        OrganizationAudit.entity_id.in_(ids), OrganizationAudit.actor_id != run_id
                    )
                ):
                    raise ValueError("Another actor modified a test resource")
                secondary = session.get(Account, secondary_id)
                if secondary and (
                    secondary.issuer != ISSUER
                    or len(secondary.grants) != 1
                    or secondary.grants[0].role != "EMPLOYEE"
                    or secondary.profile
                    and secondary.profile.id not in employee_ids
                ):
                    raise ValueError("Secondary account ownership mismatch")
                result = {
                    "employees": [
                        {
                            "id": r.id,
                            "name": r.display_name,
                            "accountId": r.account_id,
                            "version": r.version,
                        }
                        for r in employees
                    ],
                    "accountId": secondary_id,
                    "subject": secondary.subject if secondary else None,
                    "auditCount": len(records),
                }
                if action == "organization_cleanup":
                    for model, column in (
                        (Department, EmployeeProfile.department_id),
                        (JobTitle, EmployeeProfile.job_title_id),
                        (EmployeeProfile, EmployeeProfile.manager_id),
                    ):
                        targets = [r.id for r in groups[model]]
                        if session.scalar(
                            select(EmployeeProfile.id).where(
                                column.in_(targets), EmployeeProfile.id.not_in(employee_ids)
                            )
                        ):
                            raise ValueError("A non-owned employee references a test resource")
                    for r in employees:
                        r.manager_id = None
                    session.flush()
                    for r in records:
                        session.delete(r)
                    for r in employees:
                        session.delete(r)
                    session.flush()
                    for model in (Department, JobTitle):
                        for r in groups[model]:
                            session.delete(r)
                    if secondary:
                        session.execute(
                            delete(CompanyRoleGrant).where(
                                CompanyRoleGrant.account_id == secondary_id
                            )
                        )
                        session.execute(delete(Account).where(Account.id == secondary_id))
                    session.flush()
                    session.expire_all()
                    if (
                        any(
                            session.scalar(select(model.id).where(model.id.in_(ids)))
                            for model in groups
                        )
                        or session.get(Account, secondary_id)
                        or session.scalar(
                            select(OrganizationAudit.id).where(OrganizationAudit.actor_id == run_id)
                        )
                    ):
                        raise ValueError("Organization cleanup incomplete")
                    result["cleaned"] = True
                print(json.dumps(result))
                return
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
                        issuer=ISSUER,
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
