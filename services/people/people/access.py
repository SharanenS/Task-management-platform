"""Resolve current authority from authoritative data on every request."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from taskspace_security.tokens import Identity

from .models import Account

COMPANY_ROLES = frozenset({"ADMIN", "MANAGER", "EMPLOYEE", "HR"})


class AccessDenied(Exception):
    pass


@dataclass(frozen=True)
class Actor:
    account_id: str
    employee_id: str
    display_name: str
    company_roles: tuple[str, ...]
    permissions: tuple[str, ...]


def resolve_actor(session: Session, identity: Identity) -> Actor:
    account = session.scalar(
        select(Account)
        .where(Account.issuer == identity.issuer, Account.subject == identity.subject)
        .options(selectinload(Account.profile), selectinload(Account.grants))
    )
    if not account or not account.active or not account.profile or not account.profile.active:
        raise AccessDenied()
    roles = tuple(sorted(g.role for g in account.grants))
    if len(roles) != 1 or not set(roles).issubset(COMPANY_ROLES):
        raise AccessDenied()
    # Company roles grant no project membership, leadership or business authority.
    return Actor(
        account.id, account.profile.id, account.profile.display_name, roles, ("account:self:read",)
    )
