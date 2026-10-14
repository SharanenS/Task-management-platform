from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.admin_service import (
    AdminError,
    get_employee_detail,
    list_employees,
    provision_employee,
    reconcile_employee,
    set_employee_active,
    update_role,
)
from app.db import Base
from app.keycloak_admin import KeycloakCollisionError, KeycloakUnavailableError, KeycloakUser
from app.models import ApplicationRole, Employee, ProvisioningStatus


class FakeKeycloak:
    def __init__(self) -> None:
        self.users: dict[str, tuple[str, str]] = {}
        self.enabled: dict[str, bool] = {}
        self.fail_create = False
        self.fail_enable = False
        self.collision = False
        self.calls: list[tuple[str, bool]] = []

    def find_owned_user(self, username: str, ownership_key: str) -> KeycloakUser | None:
        current = self.users.get(username)
        if current and current[1] == ownership_key:
            return KeycloakUser(subject=current[0], ownership_key=ownership_key)
        return None

    def create_disabled_user(self, **values: str) -> str:
        if self.collision:
            raise KeycloakCollisionError
        if self.fail_create:
            raise KeycloakUnavailableError
        subject = f"kc-{values['username']}"
        self.users[values["username"]] = (subject, values["ownership_key"])
        self.enabled[subject] = False
        return subject

    def set_enabled(self, subject: str, enabled: bool) -> None:
        self.calls.append((subject, enabled))
        if self.fail_enable:
            raise KeycloakUnavailableError
        self.enabled[subject] = enabled


@pytest.fixture
def factory() -> Generator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.drop_all(engine)


def add_employee(
    session: Session,
    subject: str,
    role: ApplicationRole = ApplicationRole.MEMBER,
    *,
    active: bool = True,
) -> Employee:
    employee = Employee(
        keycloak_subject=subject,
        username=subject,
        email=f"{subject}@example.test",
        display_name=subject.replace("-", " ").title(),
        role=role,
        active=active,
    )
    session.add(employee)
    session.commit()
    return employee


def test_directory_is_filtered_paginated_and_admin_only(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        add_employee(session, "admin", ApplicationRole.ADMIN)
        add_employee(session, "alex-manager", ApplicationRole.MANAGER)
        add_employee(session, "alex-member")
        first = list_employees(
            session, "admin", first=1, after=None, search="alex", role=None, active=True
        )
        assert len(first.items) == 1
        assert first.has_next_page is True
        second = list_employees(
            session,
            "admin",
            first=1,
            after=first.next_cursor,
            search="alex",
            role=None,
            active=True,
        )
        assert len(second.items) == 1
        with pytest.raises(AdminError, match="Administrator"):
            list_employees(
                session,
                "alex-member",
                first=20,
                after=None,
                search=None,
                role=None,
                active=None,
            )


def test_provisioning_is_idempotent_and_password_is_not_persisted(
    factory: sessionmaker[Session],
) -> None:
    keycloak = FakeKeycloak()
    with factory() as session:
        add_employee(session, "admin", ApplicationRole.ADMIN)
        values = dict(
            idempotency_key="request-1234",
            username="new.user",
            email="new.user@example.test",
            display_name="New User",
            role=ApplicationRole.MEMBER,
            active=True,
            temporary_password="temporary-password",
            keycloak=keycloak,
        )
        created = provision_employee(session, "admin", **values)
        repeated = provision_employee(session, "admin", **values)
        assert repeated.id == created.id
        assert created.active is True
        assert created.provisioning_status == ProvisioningStatus.COMPLETE
        assert not hasattr(created, "temporary_password")
        assert len(list(session.scalars(select(Employee)))) == 2


def test_provisioning_failures_are_safe_and_recoverable(
    factory: sessionmaker[Session],
) -> None:
    keycloak = FakeKeycloak()
    with factory() as session:
        add_employee(session, "admin", ApplicationRole.ADMIN)
        keycloak.fail_create = True
        with pytest.raises(AdminError) as unavailable:
            provision_employee(
                session,
                "admin",
                idempotency_key="request-1234",
                username="failed.user",
                email="failed@example.test",
                display_name="Failed User",
                role=ApplicationRole.MEMBER,
                active=True,
                temporary_password="temporary-password",
                keycloak=keycloak,
            )
        assert unavailable.value.code == "SERVICE_UNAVAILABLE"
        keycloak.fail_create = False
        keycloak.fail_enable = True
        employee = provision_employee(
            session,
            "admin",
            idempotency_key="request-5678",
            username="recover.user",
            email="recover@example.test",
            display_name="Recover User",
            role=ApplicationRole.MEMBER,
            active=True,
            temporary_password="temporary-password",
            keycloak=keycloak,
        )
        assert employee.active is False
        assert employee.provisioning_status == ProvisioningStatus.RECONCILIATION_REQUIRED


def test_role_status_and_keycloak_failure_protections(factory: sessionmaker[Session]) -> None:
    keycloak = FakeKeycloak()
    with factory() as session:
        admin = add_employee(session, "admin", ApplicationRole.ADMIN)
        member = add_employee(session, "member")
        with pytest.raises(AdminError) as self_role:
            update_role(session, "admin", admin.id, ApplicationRole.MEMBER)
        assert self_role.value.code == "SELF_PROTECTED"
        with pytest.raises(AdminError) as self_active:
            set_employee_active(session, "admin", admin.id, False, keycloak=keycloak)
        assert self_active.value.code == "SELF_PROTECTED"
        keycloak.fail_enable = True
        with pytest.raises(AdminError) as failure:
            set_employee_active(session, "admin", member.id, False, keycloak=keycloak)
        assert failure.value.code == "RECONCILIATION_REQUIRED"
        session.refresh(member)
        assert member.active is False
        assert member.provisioning_status == ProvisioningStatus.RECONCILIATION_REQUIRED


def test_directory_search_filters_ordering_and_invalid_inputs(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        add_employee(session, "admin", ApplicationRole.ADMIN)
        alpha = add_employee(session, "alpha-user", ApplicationRole.MANAGER)
        alpha.display_name = "Shared Name"
        alpha.email = "alpha@sample.test"
        beta = add_employee(session, "beta-user", active=False)
        beta.display_name = "Shared Name"
        session.commit()
        for term in (" ALPHA-USER ", "ALPHA@SAMPLE.TEST", "shared name"):
            page = list_employees(
                session, "admin", first=50, after=None, search=term, role=None, active=None
            )
            assert alpha.id in {item.id for item in page.items}
        combined = list_employees(
            session,
            "admin",
            first=50,
            after=None,
            search="shared",
            role=ApplicationRole.MEMBER,
            active=False,
        )
        assert [item.id for item in combined.items] == [beta.id]
        ordered = list_employees(
            session, "admin", first=50, after=None, search=None, role=None, active=None
        )
        assert [item.id for item in ordered.items] == sorted(item.id for item in ordered.items)
        for size in (0, 51):
            with pytest.raises(AdminError) as error:
                list_employees(
                    session, "admin", first=size, after=None, search=None, role=None, active=None
                )
            assert error.value.code == "INVALID_INPUT"
        with pytest.raises(AdminError) as error:
            list_employees(
                session, "admin", first=10, after="malformed", search=None, role=None, active=None
            )
        assert error.value.code == "INVALID_INPUT"


def test_detail_missing_and_inactive_authorization(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        admin = add_employee(session, "admin", ApplicationRole.ADMIN)
        member = add_employee(session, "member")
        assert get_employee_detail(session, "admin", member.id).id == member.id
        with pytest.raises(AdminError) as missing:
            get_employee_detail(session, "admin", __import__("uuid").uuid4())
        assert missing.value.code == "NOT_FOUND"
        admin.active = False
        session.commit()
        with pytest.raises(AdminError) as forbidden:
            get_employee_detail(session, "admin", member.id)
        assert forbidden.value.code == "FORBIDDEN"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("username", "bad name"),
        ("email", "not-email"),
        ("display_name", "x"),
        ("temporary_password", "short"),
        ("idempotency_key", "short"),
    ],
)
def test_provisioning_validates_and_normalizes_inputs(
    factory: sessionmaker[Session], field: str, value: str
) -> None:
    with factory() as session:
        add_employee(session, "admin", ApplicationRole.ADMIN)
        values = {
            "idempotency_key": "request-1234",
            "username": " New.User ",
            "email": " NEW@EXAMPLE.TEST ",
            "display_name": " New User ",
            "role": ApplicationRole.MEMBER,
            "active": True,
            "temporary_password": "temporary-password",
            "keycloak": FakeKeycloak(),
        }
        values[field] = value
        with pytest.raises(AdminError) as error:
            provision_employee(session, "admin", **values)
        assert error.value.code == "INVALID_INPUT"


def test_provisioning_collisions_and_idempotency_conflict(factory: sessionmaker[Session]) -> None:
    keycloak = FakeKeycloak()
    with factory() as session:
        add_employee(session, "admin", ApplicationRole.ADMIN)
        base = dict(
            idempotency_key="request-1234",
            username="new.user",
            email="new@example.test",
            display_name="New User",
            role=ApplicationRole.MEMBER,
            active=True,
            temporary_password="temporary-password",
            keycloak=keycloak,
        )
        provision_employee(session, "admin", **base)
        with pytest.raises(AdminError) as conflict:
            provision_employee(session, "admin", **{**base, "email": "different@example.test"})
        assert conflict.value.code == "IDEMPOTENCY_CONFLICT"
        with pytest.raises(AdminError) as duplicate:
            provision_employee(session, "admin", **{**base, "idempotency_key": "request-5678"})
        assert duplicate.value.code == "DUPLICATE_EMPLOYEE"
        keycloak.collision = True
        with pytest.raises(AdminError) as collision:
            provision_employee(
                session,
                "admin",
                **{
                    **base,
                    "idempotency_key": "request-9999",
                    "username": "other.user",
                    "email": "other@example.test",
                },
            )
        assert collision.value.code == "IDENTITY_COLLISION"


def test_repeated_mutations_reconciliation_and_final_admin(factory: sessionmaker[Session]) -> None:
    keycloak = FakeKeycloak()
    with factory() as session:
        admin = add_employee(session, "admin", ApplicationRole.ADMIN)
        second_admin = add_employee(session, "second-admin", ApplicationRole.ADMIN)
        member = add_employee(session, "member")
        assert (
            update_role(session, "admin", member.id, ApplicationRole.MANAGER).role
            == ApplicationRole.MANAGER
        )
        version = member.version
        update_role(session, "admin", member.id, ApplicationRole.MANAGER)
        assert member.version == version + 1
        set_employee_active(session, "admin", member.id, False, keycloak=keycloak)
        calls = len(keycloak.calls)
        set_employee_active(session, "admin", member.id, False, keycloak=keycloak)
        assert len(keycloak.calls) == calls
        member.provisioning_status = ProvisioningStatus.RECONCILIATION_REQUIRED
        session.commit()
        reconciled = reconcile_employee(session, "admin", member.id, keycloak=keycloak)
        assert reconciled.provisioning_status == ProvisioningStatus.COMPLETE
        reconcile_employee(session, "admin", member.id, keycloak=keycloak)
        update_role(session, "admin", second_admin.id, ApplicationRole.MEMBER)
        with pytest.raises(AdminError) as final_role:
            update_role(session, "admin", admin.id, ApplicationRole.MEMBER)
        assert final_role.value.code == "SELF_PROTECTED"
