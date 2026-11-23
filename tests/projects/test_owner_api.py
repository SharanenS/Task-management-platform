import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from gateway.app import create_app as gateway_app
from project_work.app import create_app
from project_work.delivery_inputs import advance_schedule, open_escalation, record_assessment
from project_work.models import Base
from project_work.projects import ProjectActor, ProjectService
from project_work.service import CalendarService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from taskspace_security.settings import SecuritySettings
from working_calendar.test_api import headers
from working_calendar.test_calendar import config

from .test_domain import create
from .test_membership_api import gql


@pytest.fixture
def owner_api(monkeypatch):
    monkeypatch.setenv("AUTH_ALLOW_LOCAL_HTTP", "true")
    monkeypatch.setenv("PROJECT_WORK_SERVICE_KEY", "w" * 43)
    settings = SecuritySettings(
        "https://owner-api.invalid", "https://owner-api.invalid/keys", "p" * 43
    )
    owner = ProjectActor(settings.issuer, str(uuid4()), "MANAGER", "Actual owner")
    actor = {"id": owner.account_id, "role": "MANAGER", "active": True}
    verifier = SimpleNamespace(
        verify=lambda token: (
            SimpleNamespace(issuer=settings.issuer, subject="subject")
            if token == "valid"
            else (_ for _ in ()).throw(ValueError())
        )
    )

    def people(request):
        assert request.headers["x-service-key"] == settings.service_key
        assert request.headers["authorization"] == "Bearer valid"
        if not actor["active"]:
            return httpx.Response(403)
        return httpx.Response(
            200,
            json={
                "account_id": actor["id"],
                "employee_id": actor["id"],
                "display_name": "Actual actor",
                "company_roles": [actor["role"]],
                "permissions": ["account:self:read", "admin:workspace:read"]
                if actor["role"] == "ADMIN"
                else ["account:self:read"],
            },
        )

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    calendar = CalendarService(sessions)

    def calendar_authority():
        return owner.issuer, owner.account_id

    preview = calendar.preview(calendar_authority, config())
    calendar.publish(
        calendar_authority,
        {"request_id": str(uuid4()), "preview_id": preview["preview_id"], "confirm": True},
    )
    project, _ = create(ProjectService(sessions), owner)
    with TestClient(
        create_app(settings, sessions, verifier, httpx.MockTransport(people), "w" * 43)
    ) as work:

        def transport(request):
            if request.url.host == "people":
                return people(request)
            assert request.url.host == "project-work"
            r = work.request(
                request.method,
                str(request.url),
                headers=dict(request.headers),
                json=json.loads(request.content) if request.content else None,
            )
            return httpx.Response(r.status_code, json=r.json())

        with TestClient(gateway_app(settings, verifier, httpx.MockTransport(transport))) as gateway:
            yield SimpleNamespace(
                work=work, gateway=gateway, actor=actor, sessions=sessions, project=project
            )
    engine.dispose()


QUERY = (
    "query($id:ID!){ownerOversight(id:$id){currentDeadline forecastAt forecastState "
    "actualDeliveryAt escalations{id reason} history{id outcome forecastAt} "
    "project{approvedDeadline}}}"
)
MUTATION = (
    "mutation($input:RecordOwnerDecisionInput!){recordOwnerDecision(input:$input){"
    "id actorRole outcome revisedDeadline forecastAt}}"
)


def seed(fixture):
    with fixture.sessions() as s, s.begin():
        advance_schedule(s, fixture.project["id"], 0)
        assessment = record_assessment(
            s,
            fixture.project["id"],
            1,
            fixture.project["version"],
            "ASSESSED",
            "2030-01-08T12:00:00Z",
            "Fixture forecast",
            now=datetime.now(UTC),
        )
        escalation = open_escalation(
            s,
            fixture.project["id"],
            str(uuid4()),
            assessment.id,
            "Pending fixture request",
            "Delivery team",
        )
        return escalation.id


def test_public_read_and_decision_have_real_separate_deadline_and_forecast_fields(owner_api):
    f = owner_api
    empty = gql(f.gateway, QUERY, id=f.project["id"])
    assert "errors" not in empty
    assert empty["data"]["ownerOversight"]["forecastAt"] is None
    assert empty["data"]["ownerOversight"]["escalations"] == []
    escalation = seed(f)
    value = {
        "projectId": f.project["id"],
        "escalationId": escalation,
        "requestId": str(uuid4()),
        "version": 1,
        "projectVersion": f.project["version"],
        "outcome": "ACCEPT_FORECAST_LATE",
        "reason": "Record context",
        "affectedTeam": "Delivery team",
        "confirm": True,
        "previewId": None,
    }
    result = gql(f.gateway, MUTATION, input=value)
    assert "errors" not in result
    assert result["data"]["recordOwnerDecision"]["forecastAt"] is not None
    assert result["data"]["recordOwnerDecision"]["revisedDeadline"] is None
    assert gql(f.gateway, MUTATION, input=value) == result
    f.actor["role"] = "EMPLOYEE"
    assert (
        gql(f.gateway, QUERY, id=f.project["id"])["errors"][0]["extensions"]["code"] == "FORBIDDEN"
    )
    assert (
        f.work.get("/internal/project-oversight/" + f.project["id"], headers=headers()).status_code
        == 403
    )
    f.actor["role"], f.actor["id"] = "MANAGER", str(uuid4())
    assert (
        gql(f.gateway, QUERY, id=f.project["id"])["errors"][0]["extensions"]["reason"]
        == "project_not_found"
    )


@pytest.mark.parametrize(
    "credentials", [{}, {"X-Service-Key": "w" * 43}, {"Authorization": "Bearer valid"}]
)
def test_private_owner_api_requires_both_authentication_boundaries(owner_api, credentials):
    assert (
        owner_api.work.get(
            "/internal/project-oversight/" + owner_api.project["id"], headers=credentials
        ).status_code
        == 401
    )
    assert (
        owner_api.work.post(
            "/internal/project-oversight/decide",
            headers=credentials,
            json={"project_id": owner_api.project["id"]},
        ).status_code
        == 401
    )


def test_no_public_forecast_or_escalation_input_writer_and_inactive_actor_fails_closed(owner_api):
    f = owner_api
    assert (
        f.work.post(
            "/internal/project-oversight/record-assessment", headers=headers(), json={}
        ).status_code
        == 404
    )
    f.actor["active"] = False
    response = f.gateway.post(
        "/graphql",
        headers={"Authorization": "Bearer valid"},
        json={"query": QUERY, "variables": {"id": f.project["id"]}},
    )
    assert response.status_code == 403


def test_confirmed_owner_admin_policy_records_and_revokes_an_explicit_scoped_absence(owner_api):
    f = owner_api
    now = datetime.now(UTC)
    value = {
        "projectId": f.project["id"],
        "requestId": str(uuid4()),
        "projectVersion": f.project["version"],
        "scope": "REVIEWS",
        "reason": "Explicit vacancy",
        "startsAt": (now - timedelta(hours=1)).isoformat(),
        "endsAt": (now + timedelta(hours=1)).isoformat(),
        "confirm": True,
        "leaderId": None,
    }
    query = (
        "mutation($input:RecordReviewFallbackInput!){recordReviewFallback(input:$input)"
        "{id active actorId scope}}"
    )
    result = gql(f.gateway, query, input=value)
    assert "errors" not in result
    record = result["data"]["recordReviewFallback"]
    assert record["active"] and record["actorId"] == f.actor["id"]
    assert gql(f.gateway, query, input=value) == result
    revoked = gql(
        f.gateway,
        "mutation($input:RevokeReviewFallbackInput!){revokeReviewFallback(input:$input)"
        "{id active revokedBy}}",
        input={
            "projectId": f.project["id"],
            "recordId": record["id"],
            "requestId": str(uuid4()),
            "reason": "Leader availability restored",
            "confirm": True,
        },
    )
    assert "errors" not in revoked
    assert not revoked["data"]["revokeReviewFallback"]["active"]
