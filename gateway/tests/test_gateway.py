# ruff: noqa: E501
import asyncio
from pathlib import Path

import httpx
import pytest

from app.auth import AuthenticationError, Identity
from app.employee_client import (
    EmployeeAdminPage,
    EmployeeAdminProfile,
    EmployeeDomainError,
    EmployeeForbiddenError,
    EmployeeProfile,
    EmployeeUnavailableError,
)
from app.main import app
from app.schema import schema


def request(
    method: str,
    path: str,
    *,
    payload: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, path, json=payload, params=params, headers=headers)

    return asyncio.run(send())


def test_system_info_contract() -> None:
    response = request(
        "POST",
        "/graphql",
        payload={
            "query": """
      query SystemInfo { systemInfo { name version environment status } }
    """
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["systemInfo"] == {
        "name": "Enterprise Task Platform Gateway",
        "version": "0.1.0",
        "environment": "development",
        "status": "AVAILABLE",
    }
    assert response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("path,status", [("/health/live", "alive"), ("/health/ready", "ready")])
def test_health(path: str, status: str) -> None:
    assert request("GET", path).json() == {"status": status}


def test_schema_export_matches_runtime() -> None:
    assert Path("schema.graphql").read_text(encoding="utf-8") == schema.as_str() + "\n"


def test_invalid_queries_are_sanitized() -> None:
    result = request("POST", "/graphql", payload={"query": "{ employees { password } }"}).json()
    assert result["errors"] == [{"message": "Invalid GraphQL request."}]
    assert result.get("data") is None


def test_alias_abuse_is_rejected() -> None:
    fields = " ".join(f"a{i}: systemInfo {{ status }}" for i in range(11))
    result = request("POST", "/graphql", payload={"query": "{" + fields + "}"}).json()
    assert result["errors"]
    assert result.get("data") is None


def test_get_queries_are_disabled() -> None:
    response = request("GET", "/graphql", params={"query": "{ systemInfo { status } }"})
    assert response.status_code == 400


def test_me_requires_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(_: str | None) -> Identity:
        raise AuthenticationError

    monkeypatch.setattr("app.schema.token_validator.validate", reject)
    result = request("POST", "/graphql", payload={"query": "{ me { id } }"}).json()
    assert result["errors"] == [
        {
            "message": "Authentication is required.",
            "extensions": {"code": "UNAUTHENTICATED"},
        }
    ]


def test_me_returns_employee_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.schema.token_validator.validate", lambda _: Identity(subject="subject-1")
    )

    async def employee(_: str) -> EmployeeProfile:
        return EmployeeProfile(
            id="f45e9d94-f915-4b8b-ab9b-d34912ef582c",
            display_name="Avery Morgan",
            email="avery@example.test",
            role="MANAGER",
        )

    monkeypatch.setattr("app.schema.get_employee", employee)
    result = request(
        "POST",
        "/graphql",
        payload={"query": "{ me { id displayName email role } }"},
        headers={"Authorization": "Bearer test-token"},
    ).json()
    assert result["data"]["me"] == {
        "id": "f45e9d94-f915-4b8b-ab9b-d34912ef582c",
        "displayName": "Avery Morgan",
        "email": "avery@example.test",
        "role": "MANAGER",
    }


@pytest.mark.parametrize(
    ("error", "code", "message"),
    [
        (EmployeeForbiddenError(), "FORBIDDEN", "Access is not available for this account."),
        (
            EmployeeUnavailableError(),
            "SERVICE_UNAVAILABLE",
            "Employee profiles are temporarily unavailable.",
        ),
    ],
)
def test_me_sanitizes_employee_failures(
    monkeypatch: pytest.MonkeyPatch, error: Exception, code: str, message: str
) -> None:
    monkeypatch.setattr(
        "app.schema.token_validator.validate", lambda _: Identity(subject="subject-1")
    )

    async def employee(_: str) -> EmployeeProfile:
        raise error

    monkeypatch.setattr("app.schema.get_employee", employee)
    result = request(
        "POST",
        "/graphql",
        payload={"query": "{ me { id } }"},
        headers={"Authorization": "Bearer x"},
    ).json()
    assert result["errors"] == [{"message": message, "extensions": {"code": code}}]


@pytest.mark.parametrize("role", ["MEMBER", "MANAGER"])
def test_employee_directory_rejects_non_admin(monkeypatch: pytest.MonkeyPatch, role: str) -> None:
    monkeypatch.setattr(
        "app.schema.token_validator.validate", lambda _: Identity(subject="subject-1")
    )

    async def actor(_: str) -> EmployeeProfile:
        return EmployeeProfile(id="id", display_name="User", email="user@example.test", role=role)

    monkeypatch.setattr("app.schema.get_employee", actor)
    result = request(
        "POST",
        "/graphql",
        payload={"query": "{ employees(first: 10) { nodes { id } } }"},
        headers={"Authorization": "Bearer test"},
    ).json()
    assert result["errors"][0]["extensions"]["code"] == "FORBIDDEN"


def test_employee_directory_returns_typed_admin_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.schema.token_validator.validate", lambda _: Identity(subject="admin-subject")
    )

    async def actor(_: str) -> EmployeeProfile:
        return EmployeeProfile(
            id="admin-id", display_name="Admin", email="admin@example.test", role="ADMIN"
        )

    async def directory(*_: object, **__: object) -> EmployeeAdminPage:
        return EmployeeAdminPage(
            items=[
                EmployeeAdminProfile(
                    id="employee-id",
                    username="employee.user",
                    display_name="Employee User",
                    email="employee@example.test",
                    role="MEMBER",
                    active=True,
                    provisioning_status="COMPLETE",
                    created_at="2026-10-14T00:00:00+00:00",
                    updated_at="2026-10-14T00:00:00+00:00",
                    version=1,
                )
            ],
            next_cursor=None,
            has_next_page=False,
        )

    monkeypatch.setattr("app.schema.get_employee", actor)
    monkeypatch.setattr("app.schema.list_admin_employees", directory)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": """
            { employees(first: 10) {
              nodes { id username displayName email role active provisioningStatus }
              pageInfo { hasNextPage endCursor }
            } }
            """
        },
        headers={"Authorization": "Bearer test"},
    ).json()
    assert result["data"]["employees"]["nodes"][0]["username"] == "employee.user"
    assert result["data"]["employees"]["pageInfo"]["hasNextPage"] is False


def test_employee_directory_validates_page_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.schema.token_validator.validate", lambda _: Identity(subject="admin-subject")
    )

    async def actor(_: str) -> EmployeeProfile:
        return EmployeeProfile(
            id="admin-id", display_name="Admin", email="admin@example.test", role="ADMIN"
        )

    monkeypatch.setattr("app.schema.get_employee", actor)
    result = request(
        "POST",
        "/graphql",
        payload={"query": "{ employees(first: 51) { nodes { id } } }"},
        headers={"Authorization": "Bearer test"},
    ).json()
    assert result["errors"]


def admin_profile() -> EmployeeAdminProfile:
    return EmployeeAdminProfile(
        id="employee-id",
        username="employee.user",
        display_name="Employee User",
        email="employee@example.test",
        role="MEMBER",
        active=True,
        provisioning_status="COMPLETE",
        created_at="2026-10-14T00:00:00+00:00",
        updated_at="2026-10-14T00:00:00+00:00",
        version=1,
    )


def allow_admin(monkeypatch: pytest.MonkeyPatch, role: str = "ADMIN") -> None:
    monkeypatch.setattr(
        "app.schema.token_validator.validate", lambda _: Identity(subject="actor-subject")
    )

    async def actor(_: str) -> EmployeeProfile:
        return EmployeeProfile(
            id="actor", display_name="Actor", email="actor@example.test", role=role
        )

    monkeypatch.setattr("app.schema.get_employee", actor)


@pytest.mark.parametrize(
    "query",
    [
        '{ employee(id: "employee-id") { id } }',
        'mutation { provisionEmployee(input: {idempotencyKey: "request-1234", username: "user.name", email: "user@example.test", displayName: "User Name", role: MEMBER, active: true, temporaryPassword: "temporary-password"}) { id } }',
        'mutation { updateEmployeeRole(employeeId: "employee-id", role: MANAGER) { id } }',
        'mutation { setEmployeeActive(employeeId: "employee-id", active: false) { id } }',
        'mutation { reconcileEmployee(employeeId: "employee-id") { id } }',
    ],
)
def test_every_admin_operation_rejects_unauthenticated(query: str) -> None:
    result = request("POST", "/graphql", payload={"query": query}).json()
    assert result["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize("role", ["MEMBER", "MANAGER"])
def test_direct_graphql_mutation_rejects_non_admin(
    monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    allow_admin(monkeypatch, role)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": 'mutation { setEmployeeActive(employeeId: "employee-id", active: false) { id } }'
        },
        headers={"Authorization": "Bearer forged-browser-request"},
    ).json()
    assert result["errors"][0]["extensions"]["code"] == "FORBIDDEN"


@pytest.mark.parametrize(
    ("operation", "client_name"),
    [
        (
            '{ employee(id: "employee-id") { id username role active provisioningStatus } }',
            "get_admin_employee",
        ),
        (
            'mutation { provisionEmployee(input: {idempotencyKey: "request-1234", username: "user.name", email: "user@example.test", displayName: "User Name", role: MEMBER, active: true, temporaryPassword: "temporary-password"}) { id } }',
            "provision_admin_employee",
        ),
        (
            'mutation { updateEmployeeRole(employeeId: "employee-id", role: MANAGER) { id } }',
            "update_admin_employee_role",
        ),
        (
            'mutation { setEmployeeActive(employeeId: "employee-id", active: false) { id } }',
            "update_admin_employee_active",
        ),
        (
            'mutation { reconcileEmployee(employeeId: "employee-id") { id } }',
            "reconcile_admin_employee",
        ),
    ],
)
def test_admin_employee_operations_return_typed_payloads(
    monkeypatch: pytest.MonkeyPatch, operation: str, client_name: str
) -> None:
    allow_admin(monkeypatch)

    async def client(*args: object, **kwargs: object) -> EmployeeAdminProfile:
        return admin_profile()

    monkeypatch.setattr(f"app.schema.{client_name}", client)
    result = request(
        "POST", "/graphql", payload={"query": operation}, headers={"Authorization": "Bearer token"}
    ).json()
    assert result.get("errors") is None
    assert next(iter(result["data"].values()))["id"] == "employee-id"


@pytest.mark.parametrize(
    ("error", "code", "message"),
    [
        (
            EmployeeDomainError("INVALID_INPUT", "The pagination cursor is invalid."),
            "INVALID_INPUT",
            "The pagination cursor is invalid.",
        ),
        (
            EmployeeUnavailableError(),
            "SERVICE_UNAVAILABLE",
            "Employee administration is temporarily unavailable.",
        ),
    ],
)
def test_admin_errors_are_sanitized(
    monkeypatch: pytest.MonkeyPatch, error: Exception, code: str, message: str
) -> None:
    allow_admin(monkeypatch)

    async def client(*args: object, **kwargs: object) -> EmployeeAdminProfile:
        raise error

    monkeypatch.setattr("app.schema.get_admin_employee", client)
    result = request(
        "POST",
        "/graphql",
        payload={"query": '{ employee(id: "employee-id") { id } }'},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"] == [{"message": message, "extensions": {"code": code}}]
    assert "http://employee" not in str(result)
