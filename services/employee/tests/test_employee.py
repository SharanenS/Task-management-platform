import asyncio
from collections.abc import Generator

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_session
from app.main import app
from app.models import ApplicationRole, Employee


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


def request(path: str, key: str = "") -> httpx.Response:
    async def send() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get(path, headers={"X-Internal-Service-Key": key})

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
