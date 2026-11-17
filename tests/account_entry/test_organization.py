from uuid import uuid4

import pytest
from people.access import AccessDenied, resolve_actor
from people.management import AccountManagement, ManagementError
from people.models import (
    Account,
    AccountProvisioning,
    Department,
    EmployeeProfile,
    OrganizationAudit,
)
from people.organization import OrganizationManagement
from sqlalchemy import func, select
from test_access import ISSUER, provision
from test_access import sessions as sessions
from test_management import Provider, details


@pytest.fixture
def setup(sessions):
    with sessions() as s:
        admin = provision(s, role="ADMIN")
    provider = Provider()
    return OrganizationManagement(sessions, lambda: provider), sessions, admin, provider


def command(service, admin, action, **values):
    return service.change(admin, {"request_id": str(uuid4()), "action": action, **values})[
        "entity_id"
    ]


def employee(service, admin, name="Directory Person", **values):
    return command(service, admin, "EMPLOYEE_CREATE", name=name, **values)


def test_directory_first_does_not_create_account_or_authority(setup):
    service, sessions, admin, provider = setup
    person = employee(service, admin)
    with sessions() as s:
        row = s.get(EmployeeProfile, person)
        assert row.account_id is None and row.issuer == ISSUER
        assert s.scalar(select(func.count()).select_from(Account)) == 1
    assert service.workspace(admin)["unlinked_employees"] == [
        {"id": person, "display_name": "Directory Person"}
    ]
    assert provider.mail == [] and provider.users == {}


@pytest.mark.parametrize("role", ["EMPLOYEE", "MANAGER", "HR"])
def test_company_roles_cannot_manage_directory(setup, role):
    service, sessions, admin, provider = setup
    with sessions() as s:
        other = provision(s, role=role)
    with pytest.raises(AccessDenied):
        service.workspace(other)
    with pytest.raises(AccessDenied):
        employee(service, other)


def test_units_normalization_replay_archive_and_stale_edit(setup):
    service, sessions, admin, provider = setup
    value = {
        "request_id": str(uuid4()),
        "action": "UNIT_CREATE",
        "kind": "DEPARTMENT",
        "name": "  Product   Design ",
    }
    unit = service.change(admin, value)["entity_id"]
    assert service.change(admin, value)["entity_id"] == unit
    with pytest.raises(ManagementError) as error:
        command(service, admin, "UNIT_CREATE", kind="DEPARTMENT", name="product design")
    assert error.value.code == "duplicate_structure_name"
    person = employee(service, admin, department_id=unit)
    with pytest.raises(ManagementError) as error:
        command(
            service,
            admin,
            "UNIT_UPDATE",
            kind="DEPARTMENT",
            entity_id=unit,
            name="Product Design",
            active=False,
            version=1,
        )
    assert error.value.code == "structure_in_use"
    command(service, admin, "EMPLOYEE_UPDATE", entity_id=person, version=1, name="Person")
    command(
        service,
        admin,
        "UNIT_UPDATE",
        kind="DEPARTMENT",
        entity_id=unit,
        name="Product",
        active=False,
        version=1,
    )
    with pytest.raises(ManagementError) as error:
        command(
            service,
            admin,
            "UNIT_UPDATE",
            kind="DEPARTMENT",
            entity_id=unit,
            name="Stale",
            active=True,
            version=1,
        )
    assert error.value.code == "stale_structure"
    with pytest.raises(ManagementError) as error:
        employee(service, admin, department_id=unit)
    assert error.value.code == "inactive_or_invalid_structure"
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(OrganizationAudit)) == 4


def test_reporting_chain_cycle_and_self_reference_rejected_without_partial_update(setup):
    service, sessions, admin, provider = setup
    a = employee(service, admin, "A")
    b = employee(service, admin, "B", manager_id=a)
    c = employee(service, admin, "C", manager_id=b)
    for manager in (a, c):
        with pytest.raises(ManagementError) as error:
            command(
                service,
                admin,
                "EMPLOYEE_UPDATE",
                entity_id=a,
                name="Changed",
                version=1,
                manager_id=manager,
            )
        assert error.value.code == "reporting_cycle"
    with sessions() as s:
        assert s.get(EmployeeProfile, a).display_name == "A"
        assert s.get(EmployeeProfile, a).version == 1


def test_foreign_and_inactive_references_rejected(setup):
    service, sessions, admin, provider = setup
    with sessions() as s:
        foreign = Department(
            issuer="https://other.invalid", name="Foreign", normalized_name="foreign", active=True
        )
        inactive = EmployeeProfile(issuer=ISSUER, display_name="Inactive", active=False)
        s.add_all([foreign, inactive])
        s.commit()
        foreign_id, inactive_id = foreign.id, inactive.id
    for values, code in [
        ({"department_id": foreign_id}, "inactive_or_invalid_structure"),
        ({"manager_id": inactive_id}, "inactive_manager"),
        ({"manager_id": "invalid"}, "invalid_request"),
    ]:
        with pytest.raises(ManagementError) as error:
            employee(service, admin, **values)
        assert error.value.code == code


def test_title_and_reporting_changes_never_grant_roles(setup):
    service, sessions, admin, provider = setup
    title = command(service, admin, "UNIT_CREATE", kind="JOB_TITLE", name="Manager")
    with sessions() as s:
        identity = provision(s)
        actor = resolve_actor(s, identity)
    command(
        service,
        admin,
        "EMPLOYEE_UPDATE",
        entity_id=actor.employee_id,
        version=1,
        name="Team leader",
        job_title_id=title,
    )
    with sessions() as s:
        assert resolve_actor(s, identity).company_roles == ("EMPLOYEE",)


@pytest.mark.parametrize("enabled,exact", [(False, True), (True, False), (True, True)])
def test_link_requires_exact_active_provider_identity_and_preserves_role(setup, enabled, exact):
    service, sessions, admin, provider = setup
    person = employee(service, admin)
    with sessions() as s:
        identity = provision(s, profile=False)
        account = s.scalar(select(Account).where(Account.subject == identity.subject))
        account_id = account.id
    provider.users[identity.subject] = {
        "id": identity.subject if exact else str(uuid4()),
        "enabled": enabled,
    }
    if not (enabled and exact):
        with pytest.raises(ManagementError) as error:
            command(
                service, admin, "ACCOUNT_LINK", entity_id=person, version=1, account_id=account_id
            )
        assert error.value.code == "identity_not_active"
        with sessions() as s:
            with pytest.raises(AccessDenied):
                resolve_actor(s, identity)
    else:
        command(service, admin, "ACCOUNT_LINK", entity_id=person, version=1, account_id=account_id)
        with sessions() as s:
            actor = resolve_actor(s, identity)
            assert actor.employee_id == person and actor.company_roles == ("EMPLOYEE",)
    assert provider.mail == []


def test_create_account_attaches_existing_employee_and_recovers_without_duplicate(setup):
    service, sessions, admin, provider = setup
    person = employee(service, admin, "Existing Person")
    accounts = AccountManagement(sessions, lambda: provider)
    value = details(employee_id=person, display_name="Client name cannot overwrite directory")
    provider.fail_mail = True
    assert accounts.create(admin, value)["state"] != "COMPLETE"
    with pytest.raises(ManagementError) as error:
        command(service, admin, "EMPLOYEE_UPDATE", entity_id=person, version=2, name="Blocked")
    assert error.value.code == "employee_provisioning_pending"
    provider.fail_mail = False
    result = accounts.recover(
        admin, {"request_id": str(uuid4()), "operation_id": value["request_id"]}
    )
    assert result["state"] == "COMPLETE"
    assert accounts.create(admin, value)["state"] == "COMPLETE"
    with sessions() as s:
        op = s.get(AccountProvisioning, value["request_id"])
        assert s.get(EmployeeProfile, person).account_id == op.account_id
        assert s.get(EmployeeProfile, person).display_name == "Existing Person"
        assert s.scalar(select(func.count()).select_from(EmployeeProfile)) == 2
    assert len(provider.users) == 1 and len(provider.mail) == 1
