from datetime import datetime, timezone
from uuid import uuid4

import pytest
from people.bootstrap import ProvisioningError, ensure_initial_administrator
from people.models import Account, Base, InitialAdminProvisioning
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

ISSUER = "https://identity.example/realms/taskspace-portals"
PASSWORD = "fixture-only-strong-temporary-password"


class Provider:
    def __init__(self):
        self.users = {}
        self.created = 0
        self.passwords = {}
        self.fail_after_create = False

    def find(self, username):
        return [u for u in self.users.values() if u["username"] == username]

    def get(self, subject):
        return self.users[subject]

    def create(self, operation, password):
        subject = str(uuid4())
        self.users[subject] = {
            "id": subject,
            "username": operation.username,
            "enabled": True,
            "email": operation.email_marker,
            "firstName": "Company",
            "lastName": "Administrator",
            "createdTimestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "requiredActions": ["UPDATE_PASSWORD"],
        }
        self.created += 1
        self.passwords[subject] = password
        if self.fail_after_create:
            raise ProvisioningError("simulated_provider_response_loss")
        return subject


@pytest.fixture
def fixture():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session, Provider()
    engine.dispose()


def ensure(session, provider, password=PASSWORD):
    return ensure_initial_administrator(session, provider, ISSUER, "ADMIN", password)


def test_new_admin_has_owned_profile_single_role_and_temporary_credential(fixture):
    session, provider = fixture
    result = ensure(session, provider)
    assert result["created"] is True and provider.created == 1
    account = session.get(Account, result["accountId"])
    assert account.active and account.profile.active
    assert [g.role for g in account.grants] == ["ADMIN"]
    assert provider.users[account.subject]["requiredActions"] == ["UPDATE_PASSWORD"]
    assert session.get(InitialAdminProvisioning, "initial-admin").state == "COMPLETE"


def test_repeat_preserves_changed_password_and_exact_identity(fixture):
    session, provider = fixture
    first = ensure(session, provider)
    provider.passwords[first["subject"]] = "changed-by-the-user"
    provider.users[first["subject"]]["requiredActions"] = []
    second = ensure(session, provider, password="different-input-strong-temporary-password")
    assert second["created"] is False
    assert second["subject"] == first["subject"] and second["accountId"] == first["accountId"]
    assert provider.created == 1 and provider.passwords[first["subject"]] == "changed-by-the-user"
    assert provider.users[first["subject"]]["requiredActions"] == []


def test_existing_unrelated_identity_is_not_promoted_or_reset(fixture):
    session, provider = fixture
    subject = str(uuid4())
    provider.users[subject] = {
        "id": subject,
        "username": "admin",
        "enabled": True,
        "email": "existing@example.invalid",
    }
    with pytest.raises(ProvisioningError, match="existing_identity_not_owned"):
        ensure(session, provider)
    assert provider.created == 0 and not session.scalar(select(Account))
    assert provider.users[subject]["email"] == "existing@example.invalid"


def test_provider_response_loss_resumes_only_the_owned_operation(fixture):
    session, provider = fixture
    provider.fail_after_create = True
    with pytest.raises(ProvisioningError, match="simulated_provider_response_loss"):
        ensure(session, provider)
    session.rollback()
    provider.fail_after_create = False
    result = ensure(session, provider)
    assert result["created"] is False and result["status"] == "resumed"
    assert provider.created == 1
    assert session.get(InitialAdminProvisioning, "initial-admin").state == "COMPLETE"


@pytest.mark.parametrize("target", ["account", "profile", "identity"])
def test_inactive_existing_admin_is_never_replaced_or_reactivated(fixture, target):
    session, provider = fixture
    first = ensure(session, provider)
    account = session.get(Account, first["accountId"])
    if target == "account":
        account.active = False
    elif target == "profile":
        account.profile.active = False
    else:
        provider.users[account.subject]["enabled"] = False
    session.commit()
    with pytest.raises(ProvisioningError):
        ensure(session, provider)
    assert provider.created == 1


def test_existing_employee_account_is_not_escalated(fixture):
    session, provider = fixture
    first = ensure(session, provider)
    account = session.get(Account, first["accountId"])
    account.grants[0].role = "EMPLOYEE"
    session.commit()
    with pytest.raises(ProvisioningError, match="completed_administrator_requires_manual_recovery"):
        ensure(session, provider)
    assert account.grants[0].role == "EMPLOYEE" and provider.created == 1


def test_changed_request_does_not_adopt_pending_operation(fixture):
    session, provider = fixture
    subject = str(uuid4())
    provider.users[subject] = {"id": subject, "username": "admin"}
    with pytest.raises(ProvisioningError):
        ensure(session, provider)
    with pytest.raises(ProvisioningError, match="initial_administrator_request_changed"):
        ensure_initial_administrator(session, provider, ISSUER, "different-admin", PASSWORD)
    assert provider.created == 0
