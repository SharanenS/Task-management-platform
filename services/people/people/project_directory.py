"""Minimal active-account references for authorized project appointments."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from .access import AccessDenied, resolve_actor
from .models import Account, CompanyRoleGrant, EmployeeProfile


class ProjectDirectory:
    def __init__(self, sessions):
        self.sessions = sessions

    def lookup(self, identity, account_id=None, page=0, search=""):
        with self.sessions() as s:
            actor = resolve_actor(s, identity)
            if actor.company_roles not in {("ADMIN",), ("MANAGER",)}:
                raise AccessDenied()
            if (
                type(page) is not int
                or not 0 <= page <= 10000
                or not isinstance(search, str)
                or len(search) > 100
            ):
                raise ValueError("Invalid page")
            query = (
                select(Account)
                .join(EmployeeProfile)
                .where(
                    Account.issuer == identity.issuer,
                    EmployeeProfile.issuer == identity.issuer,
                    Account.active.is_(True),
                    EmployeeProfile.active.is_(True),
                    select(func.count())
                    .select_from(CompanyRoleGrant)
                    .where(CompanyRoleGrant.account_id == Account.id)
                    .correlate(Account)
                    .scalar_subquery()
                    == 1,
                )
                .options(selectinload(Account.profile), selectinload(Account.grants))
            )
            if account_id is not None:
                query = query.where(Account.id == str(UUID(account_id)))
            else:
                query = query.where(
                    Account.grants.any(CompanyRoleGrant.role == "EMPLOYEE"),
                    func.lower(EmployeeProfile.display_name).contains(
                        search.lower(), autoescape=True
                    ),
                )
            rows = s.scalars(
                query.order_by(EmployeeProfile.display_name, Account.id).offset(page * 25).limit(26)
            ).all()
            values = [
                {
                    "account_id": r.id,
                    "display_name": r.profile.display_name,
                    "active": True,
                    "role": r.grants[0].role,
                }
                for r in rows
                if len(r.grants) == 1 and r.grants[0].role == "EMPLOYEE"
            ]
            if account_id is not None:
                return values[0] if values else {"account_id": account_id, "active": False}
            return {"candidates": values[:25], "has_more": len(values) > 25}
