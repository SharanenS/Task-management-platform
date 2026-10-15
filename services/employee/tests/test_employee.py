import asyncio
from collections.abc import Generator
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_session
from app.main import app
from app.models import ApplicationRole, Employee, ProvisioningStatus


@pytest.fixture
def database() -> Generator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override() -> Generator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    yield factory
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def request(
    path: str,
    key: str = "",
    actor: str = "",
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(
                method,
                path,
                headers={"X-Internal-Service-Key": key, "X-Actor-Subject": actor},
                json=payload,
            )

    return asyncio.run(send())


def test_internal_contract_rejects_missing_credential(database: sessionmaker[Session]) -> None:
    assert request("/internal/employees/by-subject/subject-1").status_code == 403


def test_missing_employee_is_denied(database: sessionmaker[Session]) -> None:
    response = request("/internal/employees/by-subject/missing", settings.internal_service_key)
    assert response.status_code == 404


def test_inactive_employee_is_denied(database: sessionmaker[Session]) -> None:
    with database() as session:
        session.add(
            Employee(
                keycloak_subject="inactive",
                username="inactive",
                email="inactive@example.test",
                display_name="Inactive Employee",
                role=ApplicationRole.MEMBER,
                active=False,
            )
        )
        session.commit()
    assert (
        request(
            "/internal/employees/by-subject/inactive", settings.internal_service_key
        ).status_code
        == 404
    )


def test_active_employee_profile(database: sessionmaker[Session]) -> None:
    with database() as session:
        employee = Employee(
            keycloak_subject="active",
            username="active",
            email="active@example.test",
            display_name="Active Employee",
            role=ApplicationRole.ADMIN,
            active=True,
        )
        session.add(employee)
        session.commit()
        employee_id = str(employee.id)
    response = request("/internal/employees/by-subject/active", settings.internal_service_key)
    assert response.status_code == 200
    assert response.json() == {
        "id": employee_id,
        "display_name": "Active Employee",
        "email": "active@example.test",
        "role": "ADMIN",
    }


def add_employee(
    database: sessionmaker[Session],
    *,
    subject: str,
    role: ApplicationRole,
    active: bool = True,
    status: ProvisioningStatus = ProvisioningStatus.COMPLETE,
    display_name: str | None = None,
) -> str:
    with database() as session:
        employee = Employee(
            keycloak_subject=subject,
            username=subject,
            email=f"{subject}@example.test",
            display_name=display_name or subject.replace(".", " ").title(),
            role=role,
            active=active,
            provisioning_status=status,
        )
        session.add(employee)
        session.commit()
        return str(employee.id)


@pytest.mark.parametrize("role", [ApplicationRole.ADMIN, ApplicationRole.MANAGER])
def test_project_member_directory_allows_active_creator_roles(
    database: sessionmaker[Session], role: ApplicationRole
) -> None:
    add_employee(database, subject="actor", role=role)
    target_id = add_employee(
        database,
        subject="target",
        role=ApplicationRole.MEMBER,
        display_name="Eligible Person",
    )
    response = request(
        "/internal/project-members/eligible?first=25&search=%20eligible%20",
        settings.internal_service_key,
        "actor",
    )
    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": target_id,
                "display_name": "Eligible Person",
                "email": "target@example.test",
            }
        ],
        "next_cursor": None,
        "has_next_page": False,
    }


@pytest.mark.parametrize(
    ("role", "active", "status"),
    [
        (ApplicationRole.MEMBER, True, ProvisioningStatus.COMPLETE),
        (ApplicationRole.MANAGER, False, ProvisioningStatus.COMPLETE),
        (ApplicationRole.MANAGER, True, ProvisioningStatus.RECONCILIATION_REQUIRED),
    ],
)
def test_project_member_directory_rejects_ineligible_actor(
    database: sessionmaker[Session],
    role: ApplicationRole,
    active: bool,
    status: ProvisioningStatus,
) -> None:
    add_employee(database, subject="actor", role=role, active=active, status=status)
    response = request(
        "/internal/project-members/eligible",
        settings.internal_service_key,
        "actor",
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FORBIDDEN"


def test_project_member_directory_filters_inactive_and_incomplete_targets(
    database: sessionmaker[Session],
) -> None:
    add_employee(database, subject="actor", role=ApplicationRole.ADMIN)
    active_id = add_employee(database, subject="active.target", role=ApplicationRole.MEMBER)
    add_employee(
        database,
        subject="inactive.target",
        role=ApplicationRole.MEMBER,
        active=False,
    )
    add_employee(
        database,
        subject="incomplete.target",
        role=ApplicationRole.MEMBER,
        status=ProvisioningStatus.RECONCILIATION_REQUIRED,
    )
    response = request(
        "/internal/project-members/eligible?search=target",
        settings.internal_service_key,
        "actor",
    )
    assert [item["id"] for item in response.json()["items"]] == [active_id]


def test_project_member_directory_paginates_and_enforces_bounds(
    database: sessionmaker[Session],
) -> None:
    add_employee(database, subject="actor", role=ApplicationRole.ADMIN)
    add_employee(database, subject="one", role=ApplicationRole.MEMBER)
    add_employee(database, subject="two", role=ApplicationRole.MEMBER)
    first = request(
        "/internal/project-members/eligible?first=1",
        settings.internal_service_key,
        "actor",
    ).json()
    assert first["has_next_page"] is True
    second = request(
        f"/internal/project-members/eligible?first=1&after={first['next_cursor']}",
        settings.internal_service_key,
        "actor",
    ).json()
    assert second["items"][0]["id"] != first["items"][0]["id"]
    assert (
        request(
            "/internal/project-members/eligible?first=26",
            settings.internal_service_key,
            "actor",
        ).status_code
        == 422
    )


def test_project_member_validation_rejects_inactive_and_requires_internal_key(
    database: sessionmaker[Session],
) -> None:
    add_employee(database, subject="actor", role=ApplicationRole.MANAGER)
    inactive_id = add_employee(
        database, subject="inactive", role=ApplicationRole.MEMBER, active=False
    )
    assert (
        request(f"/internal/project-members/{inactive_id}/validate", actor="actor").status_code
        == 403
    )
    response = request(
        f"/internal/project-members/{inactive_id}/validate",
        settings.internal_service_key,
        "actor",
    )
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "EMPLOYEE_NOT_ELIGIBLE",
        "message": "Employee is not eligible for membership.",
    }


def test_project_member_batch_resolution_is_bounded_minimal_and_fail_closed(
    database: sessionmaker[Session],
) -> None:
    add_employee(database, subject="viewer", role=ApplicationRole.MEMBER)
    active_id = add_employee(database, subject="active.reference", role=ApplicationRole.MEMBER)
    inactive_id = add_employee(
        database, subject="inactive.reference", role=ApplicationRole.MEMBER, active=False
    )
    response = request(
        "/internal/project-members/resolve",
        settings.internal_service_key,
        "viewer",
        method="POST",
        payload={"employee_ids": [active_id, inactive_id]},
    )
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": active_id,
            "display_name": "Active Reference",
            "email": "active.reference@example.test",
        }
    ]
    assert set(response.json()[0]) == {"id", "display_name", "email"}
    too_many = request(
        "/internal/project-members/resolve",
        settings.internal_service_key,
        "viewer",
        method="POST",
        payload={"employee_ids": [str(uuid4()) for _ in range(51)]},
    )
    assert too_many.status_code == 422


def test_project_member_batch_resolution_rejects_inactive_viewer(
    database: sessionmaker[Session],
) -> None:
    add_employee(database, subject="inactive.viewer", role=ApplicationRole.MEMBER, active=False)
    response = request(
        "/internal/project-members/resolve",
        settings.internal_service_key,
        "inactive.viewer",
        method="POST",
        payload={"employee_ids": []},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FORBIDDEN"
