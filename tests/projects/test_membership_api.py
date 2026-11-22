import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from gateway.app import create_app as gateway_app
from project_work.app import create_app
from project_work.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from taskspace_security.settings import SecuritySettings
from working_calendar.test_api import headers

from .test_api import seed_calendar


@pytest.fixture
def membership_api(monkeypatch):
    monkeypatch.setenv("AUTH_ALLOW_LOCAL_HTTP", "true")
    monkeypatch.setenv("PROJECT_WORK_SERVICE_KEY", "w" * 43)
    settings = SecuritySettings("https://fixture.invalid", "https://fixture.invalid/keys", "p" * 43)
    owner, employee, peer = (str(uuid4()) for _ in range(3))
    actor = {"role": "ADMIN", "id": owner, "active": True}
    targets = {
        employee: {
            "account_id": employee,
            "display_name": "Employee",
            "role": "EMPLOYEE",
            "active": True,
        },
        peer: {"account_id": peer, "display_name": "Peer", "role": "EMPLOYEE", "active": True},
    }
    verifier = SimpleNamespace(
        verify=lambda token: (
            SimpleNamespace(issuer=settings.issuer, subject="subject")
            if token == "valid"
            else (_ for _ in ()).throw(ValueError())
        )
    )

    def people(request):
        assert request.url.host == "people"
        assert request.headers["x-service-key"] == settings.service_key
        assert request.headers["authorization"] == "Bearer valid"
        if not actor["active"]:
            return httpx.Response(403)
        if request.url.path == "/internal/admin/workspace" and actor["role"] != "ADMIN":
            return httpx.Response(403)
        if request.url.path == "/internal/project-candidates":
            if actor["role"] not in {"ADMIN", "MANAGER"}:
                return httpx.Response(403)
            if "account_id" in request.url.params:
                return httpx.Response(
                    200, json=targets.get(request.url.params["account_id"], {"active": False})
                )
            return httpx.Response(
                200, json={"candidates": list(targets.values()), "has_more": False}
            )
        return httpx.Response(
            200,
            json={
                "account_id": actor["id"],
                "employee_id": actor["id"],
                "display_name": "Source actor",
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
    with TestClient(
        create_app(settings, sessionmaker(engine), verifier, httpx.MockTransport(people), "w" * 43)
    ) as work:
        seed_calendar(work)
        actor["role"] = "MANAGER"
        preview = work.post(
            "/internal/projects/preview",
            headers=headers(),
            json={"name": "API project", "objectives": "Scope", "deadline_date": "2026-11-24"},
        ).json()
        project = work.post(
            "/internal/projects/create",
            headers=headers(),
            json={"request_id": str(uuid4()), "preview_id": preview["preview_id"], "confirm": True},
        ).json()

        def transport(request):
            if request.url.host == "people":
                return people(request)
            assert request.url.host == "project-work"
            response = work.request(
                request.method,
                str(request.url),
                headers=dict(request.headers),
                json=json.loads(request.content) if request.content else None,
            )
            return httpx.Response(response.status_code, json=response.json())

        with TestClient(gateway_app(settings, verifier, httpx.MockTransport(transport))) as gateway:
            yield work, gateway, actor, targets, project, employee, peer
    engine.dispose()


def change(project, account, **fields):
    return {
        "projectId": project["id"],
        "accountId": account,
        "version": project["version"],
        "requestId": str(uuid4()),
        "confirm": True,
        "action": "appoint",
        "responsibility": "LEADER",
        "duties": "Private assignment",
        **fields,
    }


def gql(client, query, **variables):
    return client.post(
        "/graphql",
        headers={"Authorization": "Bearer valid", "X-Actor-Role": "ADMIN", "X-Actor-Id": "forged"},
        json={"query": query, "variables": variables},
    ).json()


MUTATION = (
    "mutation($input:ChangeProjectMembershipInput!){"
    "changeProjectMembership(input:$input){projectId version changeId}}"
)
QUERY = (
    "query($id:ID!){projectMembership(id:$id){canManage responsibility "
    "members{accountId duties displayName} history{id before after}}}"
)


def test_private_membership_api_requires_both_credentials(membership_api):
    work, _, _, _, project, *_ = membership_api
    for supplied in (
        {},
        {"Authorization": "Bearer valid"},
        {"X-Service-Key": "w" * 43},
        {"Authorization": "Bearer forged", "X-Service-Key": "w" * 43},
    ):
        assert (
            work.get("/internal/project-memberships/" + project["id"], headers=supplied).status_code
            == 401
        )


def test_public_membership_scope_privacy_and_immediate_revocation(membership_api):
    _, gateway, actor, targets, project, employee, peer = membership_api
    result = gql(gateway, MUTATION, input=change(project, employee))
    assert "errors" not in result
    assert "errors" not in gql(
        gateway,
        MUTATION,
        input=change(project, peer, version=2, responsibility="CONTRIBUTOR", duties="Peer private"),
    )
    owner = actor["id"]
    actor.update(role="EMPLOYEE", id=employee)
    view = gql(gateway, QUERY, id=project["id"])["data"]["projectMembership"]
    assert view["responsibility"] == "LEADER" and not view["canManage"] and view["history"] == []
    assert next(r for r in view["members"] if r["displayName"] == "Peer")["duties"] is None
    assert (
        gql(gateway, MUTATION, input=change(project, peer))["errors"][0]["extensions"]["code"]
        == "FORBIDDEN"
    )
    assert (
        gql(
            gateway,
            "query($id:ID!){projectCandidates(id:$id){candidates{accountId}}}",
            id=project["id"],
        )["errors"][0]["extensions"]["code"]
        == "FORBIDDEN"
    )
    actor["active"] = False
    rejected = gateway.post(
        "/graphql",
        headers={"Authorization": "Bearer valid"},
        json={"query": QUERY, "variables": {"id": project["id"]}},
    )
    assert rejected.status_code == 403 and rejected.json().get("data") is None
    actor.update(role="MANAGER", id=owner, active=True)
    assert "errors" not in gql(
        gateway, MUTATION, input=change(project, employee, version=3, action="remove")
    )
    actor.update(role="EMPLOYEE", id=employee)
    assert (
        gql(gateway, QUERY, id=project["id"])["errors"][0]["extensions"]["reason"]
        == "project_not_found"
    )


@pytest.mark.parametrize("candidate", ["unrelated", "malformed"])
def test_non_owner_cannot_enumerate_candidates_or_change_members(membership_api, candidate):
    _, gateway, actor, _, project, employee, _ = membership_api
    actor["id"] = str(uuid4())
    project_id = "../admin/calendar" if candidate == "malformed" else project["id"]
    result = gql(
        gateway, "query($id:ID!){projectCandidates(id:$id){candidates{accountId}}}", id=project_id
    )
    assert result["errors"][0]["extensions"]["reason"] == "project_not_found"
    assert (
        gql(gateway, MUTATION, input=change(project, employee))["errors"][0]["extensions"]["reason"]
        == "project_not_found"
    )


def test_candidate_deactivation_and_hr_change_block_new_appointments(membership_api):
    _, gateway, actor, targets, project, employee, _ = membership_api
    for fields in ({"active": False}, {"active": True, "role": "HR"}):
        targets[employee].update(fields)
        result = gql(gateway, MUTATION, input=change(project, employee))
        assert result["errors"][0]["extensions"]["reason"] == "member_not_eligible"
    actor["role"] = "HR"
    assert gql(gateway, QUERY, id=project["id"])["errors"][0]["extensions"]["code"] == "FORBIDDEN"
