"""Shared company directory commands; employment metadata never grants company roles."""

import hashlib
import json
from uuid import uuid4

from sqlalchemy import func, select

from .access import COMPANY_ROLES
from .identity_admin import IdentityAdministrationError
from .management import ManagementError, identifier, management_session
from .models import (
    Account,
    AccountProvisioning,
    Department,
    EmployeeProfile,
    JobTitle,
    OrganizationAudit,
)


def clean_name(value, limit):
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        raise ManagementError("invalid_name", 400)
    name = " ".join(value.split())
    if not 1 <= len(name) <= limit:
        raise ManagementError("invalid_name", 400)
    return name


def employee_state(employee):
    return {
        "display_name": employee.display_name,
        "department_id": employee.department_id,
        "job_title_id": employee.job_title_id,
        "manager_id": employee.manager_id,
        "account_id": employee.account_id,
        "version": employee.version,
    }


class OrganizationManagement:
    def __init__(self, sessions, provider):
        self.sessions, self.provider = sessions, provider

    def workspace(self, identity, page=0, search=""):
        if (
            not isinstance(page, int)
            or isinstance(page, bool)
            or page < 0
            or page > 10000
            or len(search) > 100
        ):
            raise ManagementError("invalid_page", 400)
        with management_session(self.sessions, identity) as (s, actor):
            departments = s.scalars(
                select(Department)
                .where(Department.issuer == identity.issuer)
                .order_by(Department.normalized_name, Department.id)
            ).all()
            titles = s.scalars(
                select(JobTitle)
                .where(JobTitle.issuer == identity.issuer)
                .order_by(JobTitle.normalized_name, JobTitle.id)
            ).all()
            directory = s.scalars(
                select(EmployeeProfile)
                .where(
                    EmployeeProfile.issuer == identity.issuer,
                    func.lower(EmployeeProfile.display_name).contains(
                        search.lower(), autoescape=True
                    ),
                )
                .order_by(EmployeeProfile.display_name, EmployeeProfile.id)
                .offset(page * 25)
                .limit(26)
            ).all()
            choices = s.scalars(
                select(EmployeeProfile)
                .where(EmployeeProfile.issuer == identity.issuer, EmployeeProfile.active.is_(True))
                .order_by(EmployeeProfile.display_name, EmployeeProfile.id)
            ).all()
            accounts = s.scalars(
                select(Account)
                .where(
                    Account.issuer == identity.issuer,
                    Account.active.is_(True),
                    ~Account.profile.has(),
                )
                .order_by(Account.id)
            ).all()
            pending = set(
                s.scalars(
                    select(AccountProvisioning.employee_id).where(
                        AccountProvisioning.issuer == identity.issuer,
                        AccountProvisioning.state != "COMPLETE",
                        AccountProvisioning.employee_id.is_not(None),
                    )
                ).all()
            )
            history = s.scalars(
                select(OrganizationAudit)
                .where(OrganizationAudit.issuer == identity.issuer)
                .order_by(OrganizationAudit.created_at.desc(), OrganizationAudit.id.desc())
                .limit(25)
            ).all()

            def unit(row):
                return {
                    "id": row.id,
                    "name": row.name,
                    "active": row.active,
                    "version": row.version,
                }

            def choice(row):
                return {"id": row.id, "display_name": row.display_name}

            return {
                "departments": [unit(d) for d in departments],
                "job_titles": [unit(t) for t in titles],
                "employees": [
                    {
                        "id": e.id,
                        **employee_state(e),
                        "active": e.active,
                        "company_role": e.account.grants[0].role
                        if e.account and len(e.account.grants) == 1
                        else "",
                    }
                    for e in directory[:25]
                ],
                "has_more": len(directory) > 25,
                "manager_options": [choice(e) for e in choices],
                "unlinked_employees": [
                    choice(e) for e in choices if e.account_id is None and e.id not in pending
                ],
                "available_accounts": [
                    {"id": a.id, "company_role": a.grants[0].role}
                    for a in accounts
                    if len(a.grants) == 1 and a.grants[0].role in COMPANY_ROLES
                ],
                "history": [
                    {
                        "id": h.id,
                        "action": h.action,
                        "entity_kind": h.entity_kind,
                        "entity_name": json.loads(h.after).get(
                            "name", json.loads(h.after).get("display_name", "Employee")
                        ),
                        "actor_name": s.get(Account, h.actor_id).profile.display_name
                        if s.get(Account, h.actor_id).profile
                        else "Administrator",
                        "created_at": h.created_at.isoformat(),
                    }
                    for h in history
                ],
            }

    def _employee(self, s, issuer, value):
        employee = s.get(EmployeeProfile, identifier(value))
        if not employee or employee.issuer != issuer:
            raise ManagementError("employee_not_found", 404)
        return employee

    def _unit(self, s, issuer, model, value):
        if not value:
            return None
        row = s.get(model, identifier(value))
        if not row or row.issuer != issuer or not row.active:
            raise ManagementError("inactive_or_invalid_structure")
        return row.id

    def _manager(self, s, issuer, employee_id, manager_id):
        if not manager_id:
            return None
        current = identifier(manager_id)
        seen = {employee_id}
        while current:
            if current in seen:
                raise ManagementError("reporting_cycle")
            seen.add(current)
            row = self._employee(s, issuer, current)
            if not row.active:
                raise ManagementError("inactive_manager")
            current = row.manager_id
        return identifier(manager_id)

    def change(self, identity, value):
        request_id = identifier(value.get("request_id"))
        action = value.get("action")
        if action not in {
            "UNIT_CREATE",
            "UNIT_UPDATE",
            "EMPLOYEE_CREATE",
            "EMPLOYEE_UPDATE",
            "ACCOUNT_LINK",
        }:
            raise ManagementError("invalid_action", 400)
        intent = {
            k: value.get(k)
            for k in (
                "action",
                "entity_id",
                "kind",
                "name",
                "version",
                "active",
                "department_id",
                "job_title_id",
                "manager_id",
                "account_id",
            )
        }
        intent_hash = hashlib.sha256(json.dumps(intent, sort_keys=True).encode()).hexdigest()
        with management_session(self.sessions, identity) as (s, actor):
            previous = s.scalar(
                select(OrganizationAudit).where(OrganizationAudit.request_id == request_id)
            )
            if previous:
                if (
                    previous.actor_id != actor.account_id
                    or previous.issuer != identity.issuer
                    or previous.intent_hash != intent_hash
                ):
                    raise ManagementError("request_conflict")
                return {"entity_id": previous.entity_id, "state": "COMPLETE"}
            before = {}
            if action.startswith("UNIT_"):
                kind = value.get("kind")
                if kind not in {"DEPARTMENT", "JOB_TITLE"}:
                    raise ManagementError("invalid_structure_kind", 400)
                model = Department if kind == "DEPARTMENT" else JobTitle
                name = clean_name(value.get("name"), 100)
                normalized = name.casefold()
                row = (
                    None
                    if action == "UNIT_CREATE"
                    else s.get(model, identifier(value.get("entity_id")))
                )
                if action == "UNIT_UPDATE" and (not row or row.issuer != identity.issuer):
                    raise ManagementError("structure_not_found", 404)
                duplicate = s.scalar(
                    select(model).where(
                        model.issuer == identity.issuer, model.normalized_name == normalized
                    )
                )
                if duplicate and (not row or duplicate.id != row.id):
                    raise ManagementError("duplicate_structure_name")
                if row:
                    if value.get("version") != row.version:
                        raise ManagementError("stale_structure")
                    if not isinstance(value.get("active"), bool):
                        raise ManagementError("invalid_active_status", 400)
                    before = {"name": row.name, "active": row.active, "version": row.version}
                    column = (
                        EmployeeProfile.department_id
                        if kind == "DEPARTMENT"
                        else EmployeeProfile.job_title_id
                    )
                    if not value["active"] and s.scalar(
                        select(EmployeeProfile.id)
                        .where(
                            EmployeeProfile.issuer == identity.issuer,
                            EmployeeProfile.active.is_(True),
                            column == row.id,
                        )
                        .limit(1)
                    ):
                        raise ManagementError("structure_in_use")
                    row.active = value["active"]
                    row.version += 1
                    row.name = name
                    row.normalized_name = normalized
                else:
                    row = model(
                        id=str(uuid4()),
                        issuer=identity.issuer,
                        name=name,
                        normalized_name=normalized,
                        active=True,
                        version=1,
                    )
                    s.add(row)
                entity_id = row.id
                after = {"name": row.name, "active": row.active, "version": row.version}
            else:
                kind = "EMPLOYEE"
                row = (
                    None
                    if action == "EMPLOYEE_CREATE"
                    else self._employee(s, identity.issuer, value.get("entity_id"))
                )
                if row:
                    if value.get("version") != row.version:
                        raise ManagementError("stale_employee")
                    if s.scalar(
                        select(AccountProvisioning.id).where(
                            AccountProvisioning.employee_id == row.id,
                            AccountProvisioning.state != "COMPLETE",
                        )
                    ):
                        raise ManagementError("employee_provisioning_pending")
                    if row.account_id and (
                        not row.account or row.account.issuer != identity.issuer
                    ):
                        raise ManagementError("invalid_account_association")
                    before = employee_state(row)
                if action == "ACCOUNT_LINK":
                    if row.account_id is not None or not row.active:
                        raise ManagementError("employee_already_linked")
                    account = s.get(Account, identifier(value.get("account_id")))
                    if (
                        not account
                        or account.issuer != identity.issuer
                        or not account.active
                        or account.profile is not None
                        or len(account.grants) != 1
                        or account.grants[0].role not in COMPANY_ROLES
                    ):
                        raise ManagementError("invalid_account_association")
                    if s.scalar(
                        select(AccountProvisioning.id).where(
                            AccountProvisioning.account_id == account.id,
                            AccountProvisioning.state != "COMPLETE",
                        )
                    ):
                        raise ManagementError("employee_provisioning_pending")
                    try:
                        with self.provider() as provider:
                            user = provider.get(account.subject)
                        if user.get("id") != account.subject or not user.get("enabled"):
                            raise ManagementError("identity_not_active")
                    except IdentityAdministrationError:
                        raise ManagementError("identity_verification_unavailable", 503) from None
                    account.profile = row
                    account.version += 1
                    row.version += 1
                else:
                    name = clean_name(value.get("name"), 150)
                    department = self._unit(
                        s, identity.issuer, Department, value.get("department_id")
                    )
                    title = self._unit(s, identity.issuer, JobTitle, value.get("job_title_id"))
                    employee_id = row.id if row else str(uuid4())
                    manager = self._manager(
                        s, identity.issuer, employee_id, value.get("manager_id")
                    )
                    if row:
                        row.display_name = name
                        row.department_id = department
                        row.job_title_id = title
                        row.manager_id = manager
                        row.version += 1
                    else:
                        row = EmployeeProfile(
                            id=employee_id,
                            issuer=identity.issuer,
                            account_id=None,
                            display_name=name,
                            department_id=department,
                            job_title_id=title,
                            manager_id=manager,
                            active=True,
                            version=1,
                        )
                        s.add(row)
                s.flush()
                entity_id = row.id
                after = employee_state(row)
            s.add(
                OrganizationAudit(
                    issuer=identity.issuer,
                    request_id=request_id,
                    actor_id=actor.account_id,
                    entity_id=entity_id,
                    entity_kind=kind,
                    action=action,
                    intent_hash=intent_hash,
                    before=json.dumps(before, sort_keys=True),
                    after=json.dumps(after, sort_keys=True),
                )
            )
            s.commit()
            return {"entity_id": entity_id, "state": "COMPLETE"}
