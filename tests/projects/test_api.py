import json
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from gateway.app import create_app as gateway_app
from working_calendar.test_api import boundary as boundary
from working_calendar.test_api import headers
from working_calendar.test_calendar import config


def seed_calendar(client):
    preview = client.post(
        "/internal/admin/calendar/preview", headers=headers(), json=config()
    ).json()
    response = client.post(
        "/internal/admin/calendar/publish",
        headers=headers(),
        json={"preview_id": preview["preview_id"], "request_id": str(uuid4()), "confirm": True},
    )
    assert response.status_code == 200


def test_private_project_scope_live_role_checks_and_no_actor_impersonation(boundary):
    client, role, account_id, *_ = boundary
    seed_calendar(client)
    role["value"] = "MANAGER"
    for supplied in ({}, {"Authorization": "Bearer valid"}, {"X-Service-Key": "w" * 43}):
        assert client.get("/internal/projects", headers=supplied).status_code == 401
    preview = client.post(
        "/internal/projects/preview",
        headers=headers(**{"X-Actor-Role": "ADMIN", "X-Actor-Id": "other"}),
        json={"name": "Project", "objectives": "Line one\nLine two", "deadline_date": "2026-11-24"},
    )
    assert preview.status_code == 200
    request = {
        "preview_id": preview.json()["preview_id"],
        "request_id": str(uuid4()),
        "confirm": True,
        "owner_id": "other",
    }
    result = client.post("/internal/projects/create", headers=headers(), json=request)
    assert result.status_code == 200
    project = result.json()
    assert project["creator_id"] == project["owner_id"] == account_id
    role["account_id"] = str(uuid4())
    assert client.get("/internal/projects", headers=headers()).json()["projects"] == []
    assert client.get("/internal/projects/" + project["id"], headers=headers()).status_code == 404
    role["value"] = "ADMIN"
    assert client.get("/internal/projects/" + project["id"], headers=headers()).status_code == 200
    for company_role in ("EMPLOYEE", "HR"):
        role["value"] = company_role
        assert client.get("/internal/projects", headers=headers()).status_code == 403
        assert (
            client.post("/internal/projects/create", headers=headers(), json=request).status_code
            == 403
        )
    role["value"] = "MANAGER"
    role["available"] = False
    assert client.get("/internal/projects", headers=headers()).status_code == 503


def test_public_project_contract_manager_isolation_and_invalid_identifier(boundary, monkeypatch):
    work, role, account_id, verifier, settings = boundary
    seed_calendar(work)
    role["value"] = "MANAGER"
    monkeypatch.setenv("PROJECT_WORK_SERVICE_KEY", "w" * 43)

    def route(request):
        if request.url.host == "people":
            return httpx.Response(
                200,
                json={
                    "account_id": role.get("account_id", account_id),
                    "employee_id": account_id,
                    "display_name": "Source actor",
                    "company_roles": [role["value"]],
                    "permissions": ["account:self:read", "admin:workspace:read"]
                    if role["value"] == "ADMIN"
                    else ["account:self:read"],
                },
            )
        assert request.url.host == "project-work"
        response = work.request(
            request.method,
            request.url.path,
            headers=dict(request.headers),
            json=json.loads(request.content) if request.content else None,
        )
        return httpx.Response(response.status_code, json=response.json())

    with TestClient(gateway_app(settings, verifier, httpx.MockTransport(route))) as client:
        auth = {"Authorization": "Bearer valid", "X-Actor-Role": "ADMIN"}
        preview = client.post(
            "/graphql",
            headers=auth,
            json={
                "query": (
                    "mutation($input: ProjectPreviewInput!) { "
                    "previewProject(input:$input) { previewId } }"
                ),
                "variables": {
                    "input": {"name": "Owned", "objectives": "Result", "deadlineDate": "2026-11-24"}
                },
            },
        ).json()
        assert "errors" not in preview
        created = client.post(
            "/graphql",
            headers=auth,
            json={
                "query": (
                    "mutation($input: CreateProjectInput!) { "
                    "createProject(input:$input) { id creatorId ownerId } }"
                ),
                "variables": {
                    "input": {
                        "requestId": str(uuid4()),
                        "previewId": preview["data"]["previewProject"]["previewId"],
                        "confirm": True,
                    }
                },
            },
        ).json()
        assert "errors" not in created
        project_id = created["data"]["createProject"]["id"]
        role["account_id"] = str(uuid4())
        for candidate in (project_id, "../admin/calendar", str(uuid4())):
            result = client.post(
                "/graphql",
                headers=auth,
                json={
                    "query": "query($id:ID!){project(id:$id){id name}}",
                    "variables": {"id": candidate},
                },
            ).json()
            assert result["errors"][0]["extensions"]["code"] == "PROJECT_REJECTED"
            assert result["errors"][0]["extensions"]["reason"] == "project_not_found"
        result = client.post(
            "/graphql", headers=auth, json={"query": "{projectWorkspace {projects{id} hasMore}}"}
        ).json()
        assert result["data"]["projectWorkspace"] == {"projects": [], "hasMore": False}
        for company_role in ("EMPLOYEE", "HR"):
            role["value"] = company_role
            result = client.post(
                "/graphql", headers=auth, json={"query": "{projectWorkspace {projects{id}}}"}
            ).json()
            assert result["errors"][0]["extensions"]["code"] == "FORBIDDEN"
