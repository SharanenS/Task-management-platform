from uuid import uuid4

import pytest
from people.access import AccessDenied, resolve_actor
from people.models import Account, Base, CompanyRoleGrant, EmployeeProfile
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from taskspace_security.tokens import Identity

ISSUER = "https://identity.example/realms/taskspace-portals"


@pytest.fixture
def sessions():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield sessionmaker(engine)
    engine.dispose()


def provision(
    session, *, subject=None, role="EMPLOYEE", profile=True, active=True, profile_active=True
):
    account = Account(issuer=ISSUER, subject=subject or str(uuid4()), active=active)
    if profile:
        account.profile = EmployeeProfile(display_name="Test Account", active=profile_active)
    if role:
        account.grants = [CompanyRoleGrant(role=role)]
    session.add(account)
    session.commit()
    return Identity(ISSUER, account.subject)


@pytest.mark.parametrize(
    "options", [{"profile": False}, {"active": False}, {"profile_active": False}, {"role": None}]
)
def test_incomplete_or_inactive_association_is_denied(sessions, options):
    with sessions() as s:
        identity = provision(s, **options)
        with pytest.raises(AccessDenied):
            resolve_actor(s, identity)


def test_missing_and_wrong_issuer_cannot_claim_existing_account(sessions):
    with sessions() as s:
        identity = provision(s)
        for other in (
            Identity(ISSUER, "missing"),
            Identity("https://other.example", identity.subject),
        ):
            with pytest.raises(AccessDenied):
                resolve_actor(s, other)


@pytest.mark.parametrize("role", ["ADMIN", "MANAGER", "EMPLOYEE", "HR"])
def test_company_role_grants_only_implemented_non_project_capabilities(sessions, role):
    with sessions() as s:
        identity = provision(s, role=role)
        actor = resolve_actor(s, identity)
        assert actor.company_roles == (role,)
        assert actor.permissions == (
            ("account:self:read", "admin:workspace:read")
            if role == "ADMIN"
            else ("account:self:read",)
        )


def test_changes_are_observed_without_reissuing_identity_token(sessions):
    with sessions() as s:
        identity = provision(s)
        account_id = resolve_actor(s, identity).account_id
    with sessions() as s:
        account = s.get(Account, account_id)
        account.active = False
        s.commit()
    with sessions() as s:
        with pytest.raises(AccessDenied):
            resolve_actor(s, identity)
    with sessions() as s:
        account = s.get(Account, account_id)
        account.active = True
        account.grants[0].role = "HR"
        s.commit()
    with sessions() as s:
        assert resolve_actor(s, identity).company_roles == ("HR",)


def test_database_prevents_duplicate_identity_and_global_leader_role(sessions):
    with sessions() as s:
        identity = provision(s)
        s.add(Account(issuer=ISSUER, subject=identity.subject))
        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()
        with pytest.raises(IntegrityError):
            provision(s, role="TEAM_LEADER")


def test_one_company_role_per_account_is_enforced_in_database(sessions):
    with sessions() as session:
        identity = provision(session)
        actor = resolve_actor(session, identity)
        session.add(CompanyRoleGrant(account_id=actor.account_id, role="MANAGER"))
        with pytest.raises(IntegrityError):
            session.commit()
