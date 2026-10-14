import asyncio
from pathlib import Path

import httpx
import pytest

from app.auth import AuthenticationError, Identity
from app.employee_client import (
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
