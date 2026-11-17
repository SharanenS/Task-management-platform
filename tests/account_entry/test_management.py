from copy import deepcopy
from uuid import uuid4

import pytest
from people.access import AccessDenied, resolve_actor
from people.identity_admin import IdentityAdministrationError
from people.management import AccountManagement, ManagementError
from people.models import Account, AccountAudit, AccountProvisioning
from sqlalchemy import select
from test_access import provision
from test_access import sessions as sessions


class Provider:
    def __init__(self):
        self.users = {}
        self.mail = []
        self.fail_mail = False
        self.fail_status = False
        self.lose_create = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def find(self, username, email):
        return [
            deepcopy(u)
            for u in self.users.values()
            if u["username"] == username or u["email"] == email
        ]

    def get(self, subject):
        return deepcopy(self.users[subject])

    def create(self, operation):
        subject = str(uuid4())
        self.users[subject] = {
            "id": subject,
            "username": operation.username,
            "email": operation.email,
            "enabled": True,
            "requiredActions": ["VERIFY_EMAIL", "UPDATE_PASSWORD"],
            "attributes": {"taskspaceProvisioningId": [operation.id]},
        }
        if self.lose_create:
            self.lose_create = False
            raise IdentityAdministrationError()
        return subject

    def email_actions(self, subject):
        if self.fail_mail:
            raise IdentityAdministrationError()
        self.mail.append(subject)

    def enabled(self, subject, active):
        if self.fail_status:
            raise IdentityAdministrationError()
        self.users[subject]["enabled"] = active

    def logout(self, subject):
        pass


@pytest.fixture
def management(sessions):
    with sessions() as s:
        admin = provision(s, role="ADMIN")
    provider = Provider()
    return AccountManagement(sessions, lambda: provider), sessions, admin, provider


def details(**values):
    return {
        "request_id": str(uuid4()),
        "username": "new.user",
        "email": "new.user@example.test",
        "display_name": "New User",
        "role": "EMPLOYEE",
        **values,
    }


def created(management):
    service, sessions, admin, provider = management
    value = details()
    result = service.create(admin, value)
    assert result["state"] == "COMPLETE"
    with sessions() as s:
        op = s.get(AccountProvisioning, value["request_id"])
        return op.account_id, op.subject


def change(account_id, action, version=1, **values):
    return {
        "request_id": str(uuid4()),
        "account_id": account_id,
        "action": action,
        "version": version,
        **values,
    }


def test_create_has_no_password_and_replay_sends_no_extra_email(management):
    service, sessions, admin, provider = management
    value = details()
    result = service.create(admin, value)
    assert result["state"] == "COMPLETE"
    assert service.create(admin, value) == result
    assert len(provider.users) == len(provider.mail) == 1
    assert "password" not in str(provider.users)
    with sessions() as s:
        op = s.get(AccountProvisioning, value["request_id"])
        account = s.get(Account, op.account_id)
        assert account.active and account.profile.active and account.grants[0].role == "EMPLOYEE"
        assert len(s.scalars(select(AccountAudit)).all()) == 2


@pytest.mark.parametrize("role", ["EMPLOYEE", "MANAGER", "HR"])
def test_company_roles_cannot_administer(management, role):
    service, sessions, admin, provider = management
    with sessions() as s:
        identity = provision(s, role=role)
    for action in (lambda: service.list(identity), lambda: service.create(identity, details())):
        with pytest.raises(AccessDenied):
            action()
    assert not provider.users


def test_email_failure_denies_access_until_explicit_recovery(management):
    service, sessions, admin, provider = management
    provider.fail_mail = True
    value = details()
    assert service.create(admin, value)["state"] == "FAILED"
    with sessions() as s:
        op = s.get(AccountProvisioning, value["request_id"])
        account = s.get(Account, op.account_id)
        assert not account.active
    provider.fail_mail = False
    result = service.recover(
        admin, {"request_id": str(uuid4()), "operation_id": value["request_id"]}
    )
    assert result["state"] == "COMPLETE" and len(provider.users) == 1


def test_lost_identity_response_resumes_only_owned_identity(management):
    service, sessions, admin, provider = management
    provider.lose_create = True
    value = details()
    assert service.create(admin, value)["state"] == "FAILED"
    assert (
        service.recover(admin, {"request_id": str(uuid4()), "operation_id": value["request_id"]})[
            "state"
        ]
        == "COMPLETE"
    )
    assert len(provider.users) == 1


def test_unrelated_identity_is_never_adopted(management):
    service, sessions, admin, provider = management
    subject = str(uuid4())
    provider.users[subject] = {
        "id": subject,
        "username": "new.user",
        "email": "new.user@example.test",
        "enabled": True,
        "attributes": {},
    }
    assert service.create(admin, details())["state"] == "FAILED"
    with sessions() as s:
        assert len(s.scalars(select(Account)).all()) == 1
        assert s.scalar(select(AccountProvisioning)).failure_code == "identity_not_owned"
    assert not provider.mail


def test_deactivation_fails_closed_and_retains_history_when_provider_unavailable(management):
    service, sessions, admin, provider = management
    account_id, subject = created(management)
    provider.fail_status = True
    assert service.change(admin, change(account_id, "DEACTIVATE"))["state"] == "FAILED"
    with sessions() as s:
        account = s.get(Account, account_id)
        assert not account.active and account.profile.active and account.version == 2
        assert account.grants[0].role == "EMPLOYEE"
    provider.fail_status = False
    assert service.change(admin, change(account_id, "DEACTIVATE", 2))["state"] == "COMPLETE"
    assert not provider.users[subject]["enabled"]
    assert service.change(admin, change(account_id, "ACTIVATE", 3))["state"] == "COMPLETE"
    assert provider.users[subject]["enabled"]


def test_stale_changes_and_request_conflicts_are_rejected(management):
    service, sessions, admin, provider = management
    account_id, subject = created(management)
    value = change(account_id, "ROLE", role="HR")
    assert service.change(admin, value)["state"] == "COMPLETE"
    assert service.change(admin, value)["state"] == "COMPLETE"
    with pytest.raises(ManagementError) as error:
        service.change(admin, change(account_id, "ROLE", role="ADMIN"))
    assert error.value.code == "stale_account"
    with pytest.raises(ManagementError) as error:
        service.create(admin, details(request_id=value["request_id"]))
    # The command id is globally unique, never reused as a creation operation.


def test_self_deactivation_and_demotion_cannot_lock_out_administrator(management):
    service, sessions, admin, provider = management
    with sessions() as s:
        account = s.scalar(select(Account).where(Account.subject == admin.subject))
        account_id = account.id
    for value in (change(account_id, "DEACTIVATE"), change(account_id, "ROLE", role="EMPLOYEE")):
        with pytest.raises(ManagementError) as error:
            service.change(admin, value)
        assert error.value.code == "self_access_change_denied"


def test_role_revocation_affects_existing_identity_and_never_employment_title(management):
    service, sessions, admin, provider = management
    account_id, subject = created(management)
    assert service.change(admin, change(account_id, "ROLE", role="ADMIN"))["state"] == "COMPLETE"
    with sessions() as s:
        from taskspace_security.tokens import Identity

        identity = Identity(admin.issuer, subject)
        assert resolve_actor(s, identity).company_roles == ("ADMIN",)
    assert service.change(admin, change(account_id, "ROLE", 2, role="HR"))["state"] == "COMPLETE"
    with pytest.raises(AccessDenied):
        service.list(identity)
    with sessions() as s:
        assert s.get(Account, account_id).profile.display_name == "New User"


def test_reset_email_is_explicit_and_replay_is_read_only(management):
    service, sessions, admin, provider = management
    account_id, subject = created(management)
    value = change(account_id, "RESET_EMAIL")
    assert service.change(admin, value)["state"] == "COMPLETE"
    assert service.change(admin, value)["state"] == "COMPLETE"
    assert provider.mail == [subject, subject]


@pytest.mark.parametrize(
    "values", [{"role": "OWNER"}, {"email": "bad"}, {"username": "../root"}, {"display_name": ""}]
)
def test_invalid_creation_has_no_provider_side_effect(management, values):
    service, sessions, admin, provider = management
    with pytest.raises(ManagementError):
        service.create(admin, details(**values))
    assert not provider.users


def test_last_administrator_constraint_is_independent_of_self_guard(management):
    from types import SimpleNamespace

    from people.management import protect_admin

    service, sessions, admin, provider = management
    with sessions() as s:
        target = s.scalar(select(Account).where(Account.subject == admin.subject))
        with pytest.raises(ManagementError) as error:
            protect_admin(s, SimpleNamespace(account_id=str(uuid4())), target, True)
        assert error.value.code == "last_administrator_required"


def test_reset_request_failure_is_audited_without_credential_write(management):
    service, sessions, admin, provider = management
    account_id, subject = created(management)
    provider.fail_mail = True
    value = change(account_id, "RESET_EMAIL")
    assert service.change(admin, value)["state"] == "FAILED"
    with sessions() as s:
        row = s.scalar(select(AccountAudit).where(AccountAudit.request_id == value["request_id"]))
        assert row.state == "FAILED" and s.get(Account, account_id).active
    assert "credentials" not in str(provider.users)


def test_interrupted_outcome_commit_cannot_activate_without_completed_history(management):
    from sqlalchemy import event
    from sqlalchemy.orm import Session

    service, sessions, admin, provider = management
    value = details()

    def remember_outcome(session, *args):
        if any(
            isinstance(row, AccountAudit) and row.action == "PROVISION" and row.state == "COMPLETE"
            for row in session.new
        ):
            session.info["interrupt_outcome"] = True

    def interrupt(session):
        if session.info.get("interrupt_outcome") or any(
            isinstance(row, AccountAudit) and row.action == "PROVISION" and row.state == "COMPLETE"
            for row in session.new
        ):
            raise RuntimeError("simulated outcome commit interruption")

    event.listen(Session, "before_flush", remember_outcome)
    event.listen(Session, "before_commit", interrupt)
    try:
        with pytest.raises(RuntimeError, match="simulated outcome commit interruption"):
            service.create(admin, value)
    finally:
        event.remove(Session, "before_commit", interrupt)
        event.remove(Session, "before_flush", remember_outcome)
    with sessions() as s:
        operation = s.get(AccountProvisioning, value["request_id"])
        assert operation.state == "PENDING_EMAIL"
        assert not s.get(Account, operation.account_id).active
        assert not s.scalar(
            select(AccountAudit).where(
                AccountAudit.action == "PROVISION", AccountAudit.state == "COMPLETE"
            )
        )
    assert (
        service.recover(admin, {"request_id": str(uuid4()), "operation_id": value["request_id"]})[
            "state"
        ]
        == "COMPLETE"
    )
