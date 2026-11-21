from types import SimpleNamespace
from uuid import uuid4

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from project_work.app import create_app
from project_work.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from taskspace_security.settings import SecuritySettings

from .test_calendar import config


@pytest.fixture
def boundary(monkeypatch):
    monkeypatch.setenv("AUTH_ALLOW_LOCAL_HTTP", "true")
    settings = SecuritySettings("https://fixture.invalid", "https://fixture.invalid/keys", "p" * 43)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    role = {"value": "ADMIN", "available": True, "calls": 0}
    account_id = str(uuid4())

    def people(request):
        role["calls"] += 1
        assert request.url.path in {"/internal/actor", "/internal/admin/workspace"}
        assert request.url.host == "people"
        assert (
            request.headers["authorization"] == "Bearer valid"
            and request.headers["x-service-key"] == settings.service_key
        )
        if not role["available"]:
            return httpx.Response(503)
        if request.url.path == "/internal/admin/workspace" and role["value"] != "ADMIN":
            return httpx.Response(403)
        return httpx.Response(
            200,
            json={
                "account_id": role.get("account_id", account_id),
                "employee_id": role.get("account_id", account_id),
                "display_name": "Source actor",
                "company_roles": [role["value"]],
                "permissions": ["account:self:read", "admin:workspace:read"]
                if role["value"] == "ADMIN"
                else ["account:self:read"],
            },
        )

    def verify(token):
        if token != "valid":
            raise jwt.InvalidTokenError()
        return SimpleNamespace(issuer=settings.issuer, subject=str(uuid4()))

    app = create_app(
        settings,
        sessionmaker(engine),
        SimpleNamespace(verify=verify),
        httpx.MockTransport(people),
        "w" * 43,
    )
    with TestClient(app) as client:
        yield client, role, account_id, SimpleNamespace(verify=verify), settings
    engine.dispose()


def headers(**extra):
    return {"Authorization": "Bearer valid", "X-Service-Key": "w" * 43, **extra}


def test_private_api_requires_both_credentials_and_does_not_trust_actor_headers(boundary):
    client, role, *_ = boundary
    for supplied in (
        {},
        {"Authorization": "Bearer valid"},
        {"X-Service-Key": "w" * 43},
        {"Authorization": "Bearer forged", "X-Service-Key": "w" * 43},
    ):
        assert client.get("/internal/admin/calendar", headers=supplied).status_code == 401
    for company_role in ("EMPLOYEE", "MANAGER", "HR"):
        role["value"] = company_role
        assert (
            client.get(
                "/internal/admin/calendar", headers=headers(**{"X-Actor-Role": "ADMIN"})
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/internal/admin/calendar/preview", json=config(), headers=headers()
            ).status_code
            == 403
        )
    role["value"] = "ADMIN"
    assert client.get("/internal/admin/calendar", headers=headers()).json() == {
        "current": None,
        "history": [],
    }


def test_revocation_and_authority_outage_fail_closed_before_publication(boundary):
    client, role, *_ = boundary
    response = client.post("/internal/admin/calendar/preview", headers=headers(), json=config())
    assert response.status_code == 200
    preview = response.json()["preview_id"]
    role["value"] = "EMPLOYEE"
    command = {"preview_id": preview, "request_id": str(uuid4()), "confirm": True}
    assert (
        client.post("/internal/admin/calendar/publish", headers=headers(), json=command).status_code
        == 403
    )
    role["value"] = "ADMIN"
    role["available"] = False
    assert (
        client.post("/internal/admin/calendar/publish", headers=headers(), json=command).status_code
        == 503
    )
    role["available"] = True
    assert client.get("/internal/admin/calendar", headers=headers()).json()["current"] is None
    result = client.post("/internal/admin/calendar/publish", headers=headers(), json=command)
    assert result.status_code == 200
    assert result.headers["Cache-Control"] == "no-store"


def test_public_graphql_calendar_contract_and_independent_authority(boundary, monkeypatch):
    from gateway.app import create_app as gateway_app

    work, role, account_id, verifier, settings = boundary
    monkeypatch.setenv("PROJECT_WORK_SERVICE_KEY", "w" * 43)

    def route(request):
        if request.url.host == "people":
            return httpx.Response(
                200,
                json={
                    "account_id": account_id,
                    "employee_id": str(uuid4()),
                    "display_name": "Source fixture",
                    "company_roles": [role["value"]],
                    "permissions": ["account:self:read", "admin:workspace:read"]
                    if role["value"] == "ADMIN"
                    else ["account:self:read"],
                },
            )
        assert request.url.host == "project-work" and request.headers["x-service-key"] == "w" * 43
        import json

        response = work.request(
            request.method,
            request.url.path,
            headers=dict(request.headers),
            json=json.loads(request.content) if request.content else None,
        )
        return httpx.Response(response.status_code, json=response.json())

    with TestClient(gateway_app(settings, verifier, httpx.MockTransport(route))) as client:
        auth = {"Authorization": "Bearer valid"}
        result = client.post(
            "/graphql",
            headers=auth,
            json={"query": "{ companyCalendar { current { id } history { number } } }"},
        )
        assert result.json()["data"]["companyCalendar"] == {"current": None, "history": []}
        mutation = {
            "query": (
                "mutation($input: CalendarConfigurationInput!) { "
                "previewCompanyCalendar(input:$input) { previewId "
                "config { timezone week { weekday working } } } }"
            ),
            "variables": {"input": config()},
        }
        result = client.post("/graphql", headers=auth, json=mutation).json()
        assert "errors" not in result
        assert result["data"]["previewCompanyCalendar"]["config"]["timezone"] == "Asia/Colombo"
        preview_id = result["data"]["previewCompanyCalendar"]["previewId"]
        published = client.post(
            "/graphql",
            headers=auth,
            json={
                "query": "mutation($input: PublishCalendarInput!) { "
                "publishCompanyCalendar(input:$input) { id number tzdbVersion } }",
                "variables": {
                    "input": {"previewId": preview_id, "requestId": str(uuid4()), "confirm": True}
                },
            },
        ).json()
        assert "errors" not in published
        version_id = published["data"]["publishCompanyCalendar"]["id"]
        workspace = client.post(
            "/graphql",
            headers=auth,
            json={
                "query": (
                    "{ companyCalendar { current { id tzdbVersion } "
                    "history { number tzdbVersion } } }"
                )
            },
        ).json()
        assert "errors" not in workspace
        assert workspace["data"]["companyCalendar"]["history"][0]["number"] == 1
        calculation = client.post(
            "/graphql",
            headers=auth,
            json={
                "query": "query($input: WorkingDaysInput!) { calculateWorkingDays(input:$input) "
                "{ versionId dueLocal tzdbVersion } }",
                "variables": {
                    "input": {"versionId": version_id, "start": "2026-11-20", "duration": 3}
                },
            },
        ).json()
        assert "errors" not in calculation
        assert calculation["data"]["calculateWorkingDays"]["dueLocal"].startswith("2026-11-24")
        duplicate = client.post("/graphql", headers=auth, json=mutation).json()
        assert duplicate["errors"][0]["extensions"]["code"] == "CALENDAR_REJECTED"
        assert duplicate["errors"][0]["extensions"]["reason"] == "no_calendar_changes"
        for company_role in ("EMPLOYEE", "MANAGER", "HR"):
            role["value"] = company_role
            result = client.post(
                "/graphql", headers={**auth, "X-Actor-Role": "ADMIN"}, json=mutation
            ).json()
            assert result["errors"][0]["extensions"]["code"] == "FORBIDDEN"
