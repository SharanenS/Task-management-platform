"""API and RBAC tests for Project endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_project_service
from app.core.constants import ProjectStatus
from app.core.exceptions import NotFoundError
from app.core.security import AuthenticatedUser, Role
from app.main import app
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.project import ProjectService


@pytest.fixture
def mock_service():
    return AsyncMock(spec=ProjectService)


@pytest.fixture
def sample_project():
    return Project(
        id=uuid.uuid4(),
        name="Core Platform Project",
        description="Enterprise Task Processing",
        status=ProjectStatus.PLANNING,
        owner_id="keycloak-sub-admin-1",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _token_for_roles(roles: list[str], sub: str = "test-user-sub") -> dict:
    return {
        "sub": sub,
        "iss": "http://localhost:8080/realms/task-platform",
        "aud": "task-platform",
        "azp": "task-platform",
        "exp": 9999999999,
        "realm_access": {"roles": roles},
    }


# ── 1. Project creation by ADMIN ─────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_create_project_by_admin(mock_decode, mock_get_key, client, mock_service, sample_project):
    """1. Project creation by ADMIN -> 201 Created."""
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["ADMIN"], sub="admin-sub-1")
    
    mock_service.create_project.return_value = sample_project
    app.dependency_overrides[get_project_service] = lambda: mock_service

    try:
        response = await client.post(
            "/api/v1/projects",
            json={"name": "Core Platform Project", "description": "Enterprise Task Processing"},
            headers={"Authorization": "Bearer admin.token"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Core Platform Project"
        assert data["id"] == str(sample_project.id)
    finally:
        app.dependency_overrides.clear()


# ── 2. Project creation by MANAGER ───────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_create_project_by_manager(mock_decode, mock_get_key, client, mock_service, sample_project):
    """2. Project creation by MANAGER -> 201 Created."""
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["MANAGER"], sub="manager-sub-1")

    mock_service.create_project.return_value = sample_project
    app.dependency_overrides[get_project_service] = lambda: mock_service

    try:
        response = await client.post(
            "/api/v1/projects",
            json={"name": "Core Platform Project", "description": "Enterprise Task Processing"},
            headers={"Authorization": "Bearer manager.token"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Core Platform Project"
    finally:
        app.dependency_overrides.clear()


# ── 3. Project creation denied to MEMBER ──────────────────────────────────────

@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_create_project_denied_to_member(mock_decode, mock_get_key, client):
    """3. Project creation denied to MEMBER -> 403 Forbidden."""
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["MEMBER"], sub="member-sub-1")

    response = await client.post(
        "/api/v1/projects",
        json={"name": "Unauthorized Project"},
        headers={"Authorization": "Bearer member.token"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


# ── 4. owner_id comes from authenticated identity ────────────────────────────

@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_owner_id_derived_from_authenticated_sub(mock_decode, mock_get_key, client, mock_service, sample_project):
    """4. owner_id comes strictly from authenticated identity.sub."""
    expected_sub = "actual-keycloak-sub-999"
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["ADMIN"], sub=expected_sub)

    sample_project.owner_id = expected_sub
    mock_service.create_project.return_value = sample_project
    app.dependency_overrides[get_project_service] = lambda: mock_service

    try:
        response = await client.post(
            "/api/v1/projects",
            json={"name": "Owner Project", "owner_id": "malicious-spoofed-id"},
            headers={"Authorization": "Bearer admin.token"},
        )
        assert response.status_code == 201
        # Verify the service was called with owner_id = expected_sub
        call_args = mock_service.create_project.call_args
        assert call_args.kwargs["owner_id"] == expected_sub
    finally:
        app.dependency_overrides.clear()


# ── 5. Project listing for authenticated MEMBER ───────────────────────────────

@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_list_projects_by_member(mock_decode, mock_get_key, client, mock_service, sample_project):
    """5. Project listing for authenticated MEMBER -> 200 OK."""
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["MEMBER"], sub="member-sub-1")

    mock_service.list_projects.return_value = [sample_project]
    app.dependency_overrides[get_project_service] = lambda: mock_service

    try:
        response = await client.get(
            "/api/v1/projects",
            headers={"Authorization": "Bearer member.token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == sample_project.name
        assert data[0]["id"] == str(sample_project.id)
    finally:
        app.dependency_overrides.clear()


# ── 6. Project retrieval by ID ───────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_get_project_by_id(mock_decode, mock_get_key, client, mock_service, sample_project):
    """6. Project retrieval by ID -> 200 OK."""
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["MEMBER"], sub="member-sub-1")

    mock_service.get_project.return_value = sample_project
    app.dependency_overrides[get_project_service] = lambda: mock_service

    try:
        response = await client.get(
            f"/api/v1/projects/{sample_project.id}",
            headers={"Authorization": "Bearer member.token"},
        )
        assert response.status_code == 200
        assert response.json()["id"] == str(sample_project.id)
        assert response.json()["name"] == sample_project.name
    finally:
        app.dependency_overrides.clear()


# ── 7. Project retrieval of nonexistent ID returns 404 ───────────────────────

@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_get_project_not_found(mock_decode, mock_get_key, client, mock_service):
    """7. Project retrieval of nonexistent ID returns 404 Not Found."""
    random_id = uuid.uuid4()
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["ADMIN"], sub="admin-sub-1")

    mock_service.get_project.side_effect = NotFoundError(f"Project with ID '{random_id}' not found")
    app.dependency_overrides[get_project_service] = lambda: mock_service

    try:
        response = await client.get(
            f"/api/v1/projects/{random_id}",
            headers={"Authorization": "Bearer admin.token"},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


# ── 8. Project update by MANAGER ─────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_update_project_by_manager(mock_decode, mock_get_key, client, mock_service, sample_project):
    """8. Project update by MANAGER -> 200 OK."""
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["MANAGER"], sub="manager-sub-1")

    sample_project.name = "Renamed Project"
    sample_project.status = ProjectStatus.ACTIVE
    mock_service.update_project.return_value = sample_project
    app.dependency_overrides[get_project_service] = lambda: mock_service

    try:
        response = await client.patch(
            f"/api/v1/projects/{sample_project.id}",
            json={"name": "Renamed Project", "status": "ACTIVE"},
            headers={"Authorization": "Bearer manager.token"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Renamed Project"
        assert response.json()["status"] == "ACTIVE"
    finally:
        app.dependency_overrides.clear()


# ── 9. Project update denied to MEMBER ───────────────────────────────────────

@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_update_project_denied_to_member(mock_decode, mock_get_key, client):
    """9. Project update denied to MEMBER -> 403 Forbidden."""
    random_id = uuid.uuid4()
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["MEMBER"], sub="member-sub-1")

    response = await client.patch(
        f"/api/v1/projects/{random_id}",
        json={"name": "Unauthorized Update"},
        headers={"Authorization": "Bearer member.token"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


# ── 10. Project deletion by ADMIN ────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_delete_project_by_admin(mock_decode, mock_get_key, client, mock_service, sample_project):
    """10. Project deletion by ADMIN -> 204 No Content."""
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["ADMIN"], sub="admin-sub-1")

    mock_service.delete_project.return_value = None
    app.dependency_overrides[get_project_service] = lambda: mock_service

    try:
        response = await client.delete(
            f"/api/v1/projects/{sample_project.id}",
            headers={"Authorization": "Bearer admin.token"},
        )
        assert response.status_code == 204
    finally:
        app.dependency_overrides.clear()


# ── 11. Project deletion denied to MANAGER ───────────────────────────────────

@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_delete_project_denied_to_manager(mock_decode, mock_get_key, client):
    """11. Project deletion denied to MANAGER -> 403 Forbidden."""
    random_id = uuid.uuid4()
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["MANAGER"], sub="manager-sub-1")

    response = await client.delete(
        f"/api/v1/projects/{random_id}",
        headers={"Authorization": "Bearer manager.token"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


# ── 12. Project deletion denied to MEMBER ────────────────────────────────────

@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_delete_project_denied_to_member(mock_decode, mock_get_key, client):
    """12. Project deletion denied to MEMBER -> 403 Forbidden."""
    random_id = uuid.uuid4()
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["MEMBER"], sub="member-sub-1")

    response = await client.delete(
        f"/api/v1/projects/{random_id}",
        headers={"Authorization": "Bearer member.token"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


# ── Unauthenticated / Missing Token ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_projects_endpoints_require_auth(client):
    """Unauthenticated requests without token -> 401 Unauthorized."""
    random_id = uuid.uuid4()
    res_post = await client.post("/api/v1/projects", json={"name": "Test"})
    assert res_post.status_code == 401

    res_list = await client.get("/api/v1/projects")
    assert res_list.status_code == 401

    res_get = await client.get(f"/api/v1/projects/{random_id}")
    assert res_get.status_code == 401

    res_patch = await client.patch(f"/api/v1/projects/{random_id}", json={"name": "Test"})
    assert res_patch.status_code == 401

    res_delete = await client.delete(f"/api/v1/projects/{random_id}")
    assert res_delete.status_code == 401


# ── Whitespace Validation via API (422) ──────────────────────────────────────

@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_create_project_whitespace_only_name_returns_422(mock_decode, mock_get_key, client):
    """POST with whitespace-only name returns 422 Unprocessable Entity."""
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["ADMIN"], sub="admin-sub-1")

    response = await client.post(
        "/api/v1/projects",
        json={"name": "   "},
        headers={"Authorization": "Bearer admin.token"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_update_project_whitespace_only_name_returns_422(mock_decode, mock_get_key, client):
    """PATCH with whitespace-only name returns 422 Unprocessable Entity."""
    random_id = uuid.uuid4()
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["MANAGER"], sub="manager-sub-1")

    response = await client.patch(
        f"/api/v1/projects/{random_id}",
        json={"name": "   "},
        headers={"Authorization": "Bearer manager.token"},
    )
    assert response.status_code == 422
