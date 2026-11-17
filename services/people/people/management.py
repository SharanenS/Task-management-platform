"""Account lifecycle commands. Authorize under a shared lock; retain recovery and history."""

import json
import re
from contextlib import contextmanager
from uuid import UUID, uuid4, uuid5

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .access import COMPANY_ROLES, AccessDenied, resolve_actor
from .bootstrap import LOCK_KEY
from .identity_admin import IdentityAdministrationError
from .models import (
    Account,
    AccountAudit,
    AccountProvisioning,
    CompanyRoleGrant,
    EmployeeProfile,
)


class ManagementError(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status


def identifier(value):
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ManagementError("invalid_request", 400) from None


@contextmanager
def management_session(sessions, identity):
    # Session-level PostgreSQL lock survives the recovery commits around provider calls.
    # It shares the initial bootstrap lock, serializing all last-admin decisions.
    with sessions() as probe:
        engine = probe.get_bind()
    with engine.connect() as connection:
        postgres = connection.dialect.name == "postgresql"
        if postgres:
            connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": LOCK_KEY})
            connection.commit()
        try:
            with Session(bind=connection) as session:
                actor = resolve_actor(session, identity)
                if actor.company_roles != ("ADMIN",):
                    raise AccessDenied()
                yield session, actor
        finally:
            connection.rollback()
            if postgres:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
                connection.commit()


def summary(account, operation=None):
    return {
        "id": account.id,
        "display_name": account.profile.display_name,
        "active": account.active,
        "profile_active": account.profile.active,
        "role": account.grants[0].role if len(account.grants) == 1 else "",
        "version": account.version,
        "username": operation.username if operation else "",
        "email": operation.email if operation else "",
    }


def audit(
    session, request_id, actor, target, operation, action, state, before, after, *, commit=True
):
    row = AccountAudit(
        request_id=request_id,
        actor_id=actor.account_id,
        target_id=target.id if target else None,
        operation_id=operation.id if operation else None,
        action=action,
        state=state,
        before=json.dumps(before, sort_keys=True),
        after=json.dumps(after, sort_keys=True),
    )
    session.add(row)
    if commit:
        session.commit()
    return row


def check_replay(session, request_id, actor, action, target_id=None, operation_id=None):
    row = session.scalar(select(AccountAudit).where(AccountAudit.request_id == request_id))
    if row and (
        row.actor_id != actor.account_id
        or row.action != action
        or row.target_id != target_id
        or (operation_id is not None and row.operation_id != operation_id)
    ):
        raise ManagementError("request_conflict")
    return row


def protect_admin(session, actor, target, removing):
    if removing and target.id == actor.account_id:
        raise ManagementError("self_access_change_denied")
    if removing and target.active and any(g.role == "ADMIN" for g in target.grants):
        usable = session.scalars(
            select(Account)
            .join(CompanyRoleGrant)
            .join(EmployeeProfile)
            .where(
                Account.issuer == target.issuer,
                Account.active.is_(True),
                EmployeeProfile.active.is_(True),
                CompanyRoleGrant.role == "ADMIN",
            )
        ).all()
        if len(usable) <= 1:
            raise ManagementError("last_administrator_required")


def owned(user, operation):
    return (
        user.get("username", "").casefold() == operation.username
        and user.get("email", "").casefold() == operation.email
        and user.get("attributes", {}).get("taskspaceProvisioningId") == [operation.id]
    )


class AccountManagement:
    def __init__(self, sessions, provider):
        self.sessions, self.provider = sessions, provider

    def list(self, identity, page=0):
        if not isinstance(page, int) or page < 0 or page > 10000:
            raise ManagementError("invalid_page", 400)
        with management_session(self.sessions, identity) as (s, actor):
            accounts = s.scalars(
                select(Account)
                .where(Account.issuer == identity.issuer)
                .order_by(Account.created_at, Account.id)
                .offset(page * 25)
                .limit(26)
            ).all()
            operations = s.scalars(
                select(AccountProvisioning)
                .where(AccountProvisioning.issuer == identity.issuer)
                .order_by(AccountProvisioning.created_at.desc())
                .limit(25)
            ).all()
            page_operations = s.scalars(
                select(AccountProvisioning).where(
                    AccountProvisioning.account_id.in_([a.id for a in accounts[:25]])
                )
            ).all()
            by_account = {o.account_id: o for o in page_operations}
            history = s.scalars(
                select(AccountAudit)
                .join(Account, Account.id == AccountAudit.actor_id)
                .where(Account.issuer == identity.issuer)
                .order_by(AccountAudit.created_at.desc(), AccountAudit.id.desc())
                .limit(25)
            ).all()
            return {
                "accounts": [summary(a, by_account.get(a.id)) for a in accounts[:25] if a.profile],
                "has_more": len(accounts) > 25,
                "operations": [
                    {
                        "id": o.id,
                        "username": o.username,
                        "email": o.email,
                        "state": o.state,
                        "failure_code": o.failure_code,
                    }
                    for o in operations
                ],
                "history": [
                    {
                        "id": h.id,
                        "actor_id": h.actor_id,
                        "target_id": h.target_id,
                        "action": h.action,
                        "state": h.state,
                        "before": h.before,
                        "after": h.after,
                        "created_at": h.created_at.isoformat(),
                    }
                    for h in history
                ],
            }

    def create(self, identity, value):
        operation_id = identifier(value.get("request_id"))
        username = str(value.get("username", "")).strip().casefold()
        email = str(value.get("email", "")).strip().casefold()
        name = str(value.get("display_name", "")).strip()
        role = value.get("role")
        employee_id = identifier(value["employee_id"]) if value.get("employee_id") else None
        if (
            not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,99}", username)
            or not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", email)
            or len(email) > 254
            or not 1 <= len(name) <= 150
            or any(ord(c) < 32 for c in name)
            or role not in COMPANY_ROLES
        ):
            raise ManagementError("invalid_account_details", 400)
        with management_session(self.sessions, identity) as (s, actor):
            operation = s.get(AccountProvisioning, operation_id)
            if operation:
                if (
                    operation.username,
                    operation.email,
                    operation.display_name,
                    operation.role,
                    operation.issuer,
                    operation.employee_id,
                ) != (
                    username,
                    email,
                    operation.display_name if employee_id else name,
                    role,
                    identity.issuer,
                    employee_id,
                ):
                    raise ManagementError("request_conflict")
                # A repeated create is read-only. Recovery is a separate explicit command.
                return {"operation_id": operation.id, "state": operation.state}
            if s.scalar(select(AccountAudit).where(AccountAudit.request_id == operation_id)):
                raise ManagementError("request_conflict")
            if s.scalar(
                select(AccountProvisioning).where(
                    (AccountProvisioning.username == username)
                    | (AccountProvisioning.email == email)
                )
            ):
                raise ManagementError("account_already_requested")
            if employee_id:
                employee = s.get(EmployeeProfile, employee_id)
                if (
                    not employee
                    or employee.issuer != identity.issuer
                    or not employee.active
                    or employee.account_id is not None
                ):
                    raise ManagementError("invalid_employee_association")
                if s.scalar(
                    select(AccountProvisioning.id).where(
                        AccountProvisioning.employee_id == employee_id
                    )
                ):
                    raise ManagementError("employee_provisioning_pending")
                name = employee.display_name
            operation = AccountProvisioning(
                employee_id=employee_id,
                id=operation_id,
                username=username,
                email=email,
                display_name=name,
                role=role,
                issuer=identity.issuer,
                state="PENDING_IDENTITY",
            )
            s.add(operation)
            s.flush()
            audit(
                s,
                operation_id,
                actor,
                None,
                operation,
                "CREATE",
                "PENDING",
                {},
                {"role": role},
            )
            return self._provision(s, actor, operation)

    def _provision(self, s, actor, operation):
        try:
            employee = (
                s.get(EmployeeProfile, operation.employee_id) if operation.employee_id else None
            )
            if operation.employee_id and (
                not employee
                or employee.issuer != operation.issuer
                or not employee.active
                or employee.account_id not in {None, operation.account_id}
            ):
                raise ManagementError("invalid_employee_association")
            with self.provider() as provider:
                if not operation.subject:
                    matches = provider.find(operation.username, operation.email)
                    if matches:
                        if len(matches) != 1 or not owned(matches[0], operation):
                            raise ManagementError("identity_not_owned")
                        subject = matches[0]["id"]
                    else:
                        subject = provider.create(operation)
                    user = provider.get(subject)
                    if (
                        user.get("id") != subject
                        or not owned(user, operation)
                        or not user.get("enabled")
                    ):
                        raise ManagementError("identity_not_owned")
                    operation.subject = subject
                    operation.state = "PENDING_EMAIL"
                    s.commit()
                user = provider.get(operation.subject)
                if not owned(user, operation) or not user.get("enabled"):
                    raise ManagementError("identity_requires_review")
                if not operation.account_id:
                    if s.scalar(
                        select(Account).where(
                            Account.issuer == operation.issuer,
                            Account.subject == operation.subject,
                        )
                    ):
                        raise ManagementError("existing_account_requires_review")
                    account = Account(
                        id=str(uuid5(UUID(operation.id), "account")),
                        issuer=operation.issuer,
                        subject=operation.subject,
                        active=False,
                    )
                    s.add(account)
                    if employee:
                        account.profile = employee
                        employee.version += 1
                    else:
                        account.profile = EmployeeProfile(
                            id=str(uuid5(UUID(operation.id), "profile")),
                            issuer=operation.issuer,
                            display_name=operation.display_name,
                            active=True,
                        )
                    account.grants = [CompanyRoleGrant(role=operation.role)]
                    s.add(account)
                    s.flush()
                    operation.account_id = account.id
                    s.commit()
                account = s.get(Account, operation.account_id)
                # No credential exists before the recipient completes required actions.
                provider.email_actions(operation.subject)
                account.active = True
                operation.state, operation.failure_code = "COMPLETE", None
                audit(
                    s,
                    str(uuid4()),
                    actor,
                    account,
                    operation,
                    "PROVISION",
                    "COMPLETE",
                    {},
                    {"active": True, "role": operation.role},
                    commit=False,
                )
        except (IdentityAdministrationError, ManagementError) as error:
            operation.state = "FAILED"
            operation.failure_code = (
                error.code
                if isinstance(error, ManagementError)
                else "identity_or_email_unavailable"
            )
            audit(
                s,
                str(uuid4()),
                actor,
                s.get(Account, operation.account_id) if operation.account_id else None,
                operation,
                "PROVISION",
                "FAILED",
                {},
                {"reason": operation.failure_code},
                commit=False,
            )
        for pending in s.scalars(
            select(AccountAudit).where(
                AccountAudit.operation_id == operation.id, AccountAudit.state == "PENDING"
            )
        ).all():
            pending.state = "COMPLETE" if operation.state == "COMPLETE" else "FAILED"
            pending.after = json.dumps({"provisioning": operation.state}, sort_keys=True)
        s.commit()
        return {"operation_id": operation.id, "state": operation.state}

    def recover(self, identity, value):
        request_id, operation_id = (
            identifier(value.get("request_id")),
            identifier(value.get("operation_id")),
        )
        with management_session(self.sessions, identity) as (s, actor):
            operation = s.get(AccountProvisioning, operation_id)
            if not operation or operation.issuer != identity.issuer:
                raise ManagementError("not_found", 404)
            if check_replay(s, request_id, actor, "RECOVER", operation_id=operation_id):
                return {"operation_id": operation.id, "state": operation.state}
            if operation.state == "COMPLETE":
                raise ManagementError("already_complete")
            audit(s, request_id, actor, None, operation, "RECOVER", "PENDING", {}, {})
            return self._provision(s, actor, operation)

    def change(self, identity, value):
        request_id, account_id = (
            identifier(value.get("request_id")),
            identifier(value.get("account_id")),
        )
        action = value.get("action")
        if action not in {"ACTIVATE", "DEACTIVATE", "ROLE", "RESET_EMAIL"}:
            raise ManagementError("invalid_action", 400)
        with management_session(self.sessions, identity) as (s, actor):
            target = s.get(Account, account_id)
            if (
                not target
                or target.issuer != identity.issuer
                or not target.profile
                or len(target.grants) != 1
            ):
                raise ManagementError("not_found", 404)
            existing = check_replay(s, request_id, actor, action, target_id=account_id)
            if existing:
                previous = json.loads(existing.before)
                completed = json.loads(existing.after)
                if (
                    previous.get("version") != value.get("version")
                    or action == "ROLE"
                    and completed.get("role") != value.get("role")
                ):
                    raise ManagementError("request_conflict")
                return {"operation_id": existing.id, "state": existing.state}
            if value.get("version") != target.version:
                raise ManagementError("stale_account")
            role = value.get("role")
            if action == "ROLE" and role not in COMPANY_ROLES:
                raise ManagementError("invalid_role", 400)
            protect_admin(
                s,
                actor,
                target,
                action == "DEACTIVATE" or action == "ROLE" and role != "ADMIN",
            )
            if action == "ACTIVATE" and not target.profile.active:
                raise ManagementError("inactive_profile")
            operation = s.scalar(
                select(AccountProvisioning).where(AccountProvisioning.account_id == target.id)
            )
            if action == "ACTIVATE" and operation and operation.state != "COMPLETE":
                raise ManagementError("provisioning_incomplete")
            before = {
                "active": target.active,
                "role": target.grants[0].role,
                "version": target.version,
            }
            row = audit(s, request_id, actor, target, operation, action, "PENDING", before, {})
            if action == "DEACTIVATE":
                target.active = False
                target.version += 1
                s.commit()  # Application access fails closed even if the provider is unavailable.
            try:
                if action == "ROLE":
                    target.grants[0].role = role
                    target.version += 1
                else:
                    with self.provider() as provider:
                        user = provider.get(target.subject)
                        if user.get("id") != target.subject:
                            raise ManagementError("identity_requires_review")
                        if action == "RESET_EMAIL":
                            if (
                                not target.active
                                or not user.get("enabled")
                                or not user.get("email")
                            ):
                                raise ManagementError("reset_unavailable")
                            provider.email_actions(target.subject)
                        else:
                            provider.enabled(target.subject, action == "ACTIVATE")
                            if action == "DEACTIVATE":
                                provider.logout(target.subject)
                            confirmed = provider.get(target.subject)
                            if confirmed.get("enabled") != (action == "ACTIVATE"):
                                raise IdentityAdministrationError()
                            if action == "ACTIVATE":
                                target.active = True
                                target.version += 1
                row.state = "COMPLETE"
            except (IdentityAdministrationError, ManagementError):
                row.state = "FAILED"
            row.after = json.dumps(
                {
                    "active": target.active,
                    "role": target.grants[0].role,
                    "version": target.version,
                },
                sort_keys=True,
            )
            s.commit()
            return {"operation_id": row.id, "state": row.state}
