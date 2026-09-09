"""API integration tests for Job endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_job_service
from app.core.constants import JobStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.main import app
from app.models.job import Job
from app.schemas.job import JobStatusUpdate
from app.services.job import JobService


@pytest.fixture
def mock_service():
    return AsyncMock(spec=JobService)


@pytest.fixture
def sample_job():
    return Job(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        job_type="REPORT_GENERATION",
        status=JobStatus.QUEUED,
        payload={"report_type": "summary"},
        error_message=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _token_for_roles(roles: list[str], sub: str = "test-user-sub") -> dict:
    return {
        "sub": sub,
        "realm_access": {"roles": roles},
        "iss": "http://localhost:8080/realms/task-platform",
        "aud": "task-platform",
        "azp": "task-platform",
        "exp": 9999999999,
    }


# ── Unauthenticated Access ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jobs_endpoints_require_auth(client):
    random_id = uuid.uuid4()
    res_post = await client.post("/api/v1/jobs", json={"project_id": str(random_id), "job_type": "REPORT"})
    assert res_post.status_code == 401

    res_list = await client.get(f"/api/v1/jobs?project_id={random_id}")
    assert res_list.status_code == 401

    res_get = await client.get(f"/api/v1/jobs/{random_id}")
    assert res_get.status_code == 401

    res_patch = await client.patch(f"/api/v1/jobs/{random_id}/status", json={"status": "PROCESSING"})
    assert res_patch.status_code == 401


# ── Job Creation Authorization ──────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_create_job_by_manager(mock_decode, mock_get_key, client, mock_service, sample_job):
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["MANAGER"], sub="manager-1")

    mock_service.create_job.return_value = sample_job
    app.dependency_overrides[get_job_service] = lambda: mock_service

    try:
        response = await client.post(
            "/api/v1/jobs",
            json={"project_id": str(sample_job.project_id), "job_type": "REPORT_GENERATION", "payload": {"report_type": "summary"}},
            headers={"Authorization": "Bearer manager.token"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["job_type"] == "REPORT_GENERATION"
        assert data["status"] == "QUEUED"
        assert data["id"] == str(sample_job.id)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_create_job_by_admin(mock_decode, mock_get_key, client, mock_service, sample_job):
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["ADMIN"], sub="admin-1")

    mock_service.create_job.return_value = sample_job
    app.dependency_overrides[get_job_service] = lambda: mock_service

    try:
        response = await client.post(
            "/api/v1/jobs",
            json={"project_id": str(sample_job.project_id), "job_type": "REPORT_GENERATION"},
            headers={"Authorization": "Bearer admin.token"},
        )
        assert response.status_code == 201
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_create_job_denied_to_member(mock_decode, mock_get_key, client):
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["MEMBER"], sub="member-1")

    response = await client.post(
        "/api/v1/jobs",
        json={"project_id": str(uuid.uuid4()), "job_type": "REPORT"},
        headers={"Authorization": "Bearer member.token"},
    )
    assert response.status_code == 403


# ── Job Retrieval & Listing ─────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_list_jobs_by_member(mock_decode, mock_get_key, client, mock_service, sample_job):
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["MEMBER"], sub="member-1")

    mock_service.list_jobs.return_value = [sample_job]
    app.dependency_overrides[get_job_service] = lambda: mock_service

    try:
        response = await client.get(
            f"/api/v1/jobs?project_id={sample_job.project_id}",
            headers={"Authorization": "Bearer member.token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(sample_job.id)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_get_job_by_id(mock_decode, mock_get_key, client, mock_service, sample_job):
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["MEMBER"], sub="member-1")

    mock_service.get_job.return_value = sample_job
    app.dependency_overrides[get_job_service] = lambda: mock_service

    try:
        response = await client.get(
            f"/api/v1/jobs/{sample_job.id}",
            headers={"Authorization": "Bearer member.token"},
        )
        assert response.status_code == 200
        assert response.json()["id"] == str(sample_job.id)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_get_job_not_found(mock_decode, mock_get_key, client, mock_service):
    random_id = uuid.uuid4()
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["MEMBER"], sub="member-1")

    mock_service.get_job.side_effect = NotFoundError(f"Job with ID '{random_id}' not found")
    app.dependency_overrides[get_job_service] = lambda: mock_service

    try:
        response = await client.get(
            f"/api/v1/jobs/{random_id}",
            headers={"Authorization": "Bearer member.token"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


# ── Status Updates ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_update_status_by_manager(mock_decode, mock_get_key, client, mock_service, sample_job):
    """Test valid transition from QUEUED to PROCESSING by MANAGER."""
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["MANAGER"], sub="manager-1")

    # The service returns a job updated to PROCESSING
    updated_job = Job(
        id=sample_job.id,
        project_id=sample_job.project_id,
        job_type=sample_job.job_type,
        status=JobStatus.PROCESSING,
        payload=sample_job.payload,
        error_message=None,
        created_at=sample_job.created_at,
        updated_at=datetime.now(timezone.utc),
    )
    mock_service.update_status.return_value = updated_job
    app.dependency_overrides[get_job_service] = lambda: mock_service

    try:
        response = await client.patch(
            f"/api/v1/jobs/{sample_job.id}/status",
            json={"status": "PROCESSING"},
            headers={"Authorization": "Bearer manager.token"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "PROCESSING"
        mock_service.update_status.assert_called_once()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_update_status_by_admin(mock_decode, mock_get_key, client, mock_service, sample_job):
    """Test valid transition from PROCESSING to COMPLETED by ADMIN."""
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["ADMIN"], sub="admin-1")

    completed_job = Job(
        id=sample_job.id,
        project_id=sample_job.project_id,
        job_type=sample_job.job_type,
        status=JobStatus.COMPLETED,
        payload=sample_job.payload,
        error_message=None,
        created_at=sample_job.created_at,
        updated_at=datetime.now(timezone.utc),
    )
    mock_service.update_status.return_value = completed_job
    app.dependency_overrides[get_job_service] = lambda: mock_service

    try:
        response = await client.patch(
            f"/api/v1/jobs/{sample_job.id}/status",
            json={"status": "COMPLETED"},
            headers={"Authorization": "Bearer admin.token"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "COMPLETED"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_update_status_denied_to_member(mock_decode, mock_get_key, client):
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["MEMBER"], sub="member-1")

    response = await client.patch(
        f"/api/v1/jobs/{uuid.uuid4()}/status",
        json={"status": "PROCESSING"},
        headers={"Authorization": "Bearer member.token"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_update_status_invalid_transition_returns_400(mock_decode, mock_get_key, client, mock_service):
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["MANAGER"], sub="manager-1")

    mock_service.update_status.side_effect = BadRequestError("Invalid status transition from 'COMPLETED' to 'PROCESSING'")
    app.dependency_overrides[get_job_service] = lambda: mock_service

    try:
        response = await client.patch(
            f"/api/v1/jobs/{uuid.uuid4()}/status",
            json={"status": "PROCESSING"},
            headers={"Authorization": "Bearer manager.token"},
        )
        assert response.status_code == 400
        assert "Invalid status transition" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


# ── Client Input Constraints ────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_create_job_client_cannot_control_lifecycle_fields(mock_decode, mock_get_key, client, mock_service, sample_job):
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["ADMIN"], sub="admin-1")

    mock_service.create_job.return_value = sample_job
    app.dependency_overrides[get_job_service] = lambda: mock_service

    try:
        response = await client.post(
            "/api/v1/jobs",
            json={
                "project_id": str(sample_job.project_id),
                "job_type": "REPORT_GENERATION",
                "status": "COMPLETED",
                "error_message": "Hacked",
                "id": str(uuid.uuid4()),
            },
            headers={"Authorization": "Bearer admin.token"},
        )
        assert response.status_code == 201
        called_arg = mock_service.create_job.call_args[1]["data"] if "data" in mock_service.create_job.call_args[1] else mock_service.create_job.call_args[0][0]
        assert not hasattr(called_arg, "status")
        assert not hasattr(called_arg, "error_message")
        assert not hasattr(called_arg, "id")
    finally:
        app.dependency_overrides.clear()

# ── Celery Dispatch Integration ─────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_create_job_triggers_dispatcher(mock_decode, mock_get_key, client, mock_service, sample_job):
    """Creating a job calls the Celery task dispatcher with the job ID."""
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["ADMIN"], sub="admin-1")

    mock_service.create_job.return_value = sample_job
    mock_dispatcher = MagicMock()

    from app.api.deps import get_job_dispatcher
    app.dependency_overrides[get_job_service] = lambda: mock_service
    app.dependency_overrides[get_job_dispatcher] = lambda: mock_dispatcher

    try:
        response = await client.post(
            "/api/v1/jobs",
            json={"project_id": str(sample_job.project_id), "job_type": "REPORT_GENERATION"},
            headers={"Authorization": "Bearer admin.token"},
        )
        assert response.status_code == 201
        mock_dispatcher.assert_called_once_with(str(sample_job.id))
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_create_job_commit_strictly_precedes_dispatch(
    mock_decode, mock_get_key, client, mock_service, sample_job
):
    """
    Regression test: verify PostgreSQL COMMIT happens strictly BEFORE Celery dispatch.
    Invariant: Job INSERT -> DB commit -> Celery dispatch -> RabbitMQ.
    """
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["ADMIN"], sub="admin-1")

    mock_service.create_job.return_value = sample_job

    execution_order = []

    async def mock_commit():
        execution_order.append("db_commit")

    mock_session = AsyncMock()
    mock_session.commit.side_effect = mock_commit

    def mock_dispatcher(job_id: str):
        execution_order.append("celery_dispatch")

    from app.api.deps import get_db, get_job_dispatcher
    app.dependency_overrides[get_job_service] = lambda: mock_service
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_job_dispatcher] = lambda: mock_dispatcher

    try:
        response = await client.post(
            "/api/v1/jobs",
            json={"project_id": str(sample_job.project_id), "job_type": "REPORT_GENERATION"},
            headers={"Authorization": "Bearer admin.token"},
        )
        assert response.status_code == 201
        assert execution_order == ["db_commit", "celery_dispatch"], (
            f"Expected commit before dispatch, got {execution_order}"
        )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_create_job_commit_failure_aborts_dispatch(
    mock_decode, mock_get_key, client, mock_service, sample_job
):
    """
    Regression test: if database commit fails, dispatch MUST NOT be invoked.
    """
    mock_get_key.return_value = AsyncMock(key="mock-key")
    mock_decode.return_value = _token_for_roles(["ADMIN"], sub="admin-1")

    mock_service.create_job.return_value = sample_job

    mock_session = AsyncMock()
    mock_session.commit.side_effect = RuntimeError("Database commit failed")

    mock_dispatcher = MagicMock()

    from app.api.deps import get_db, get_job_dispatcher
    app.dependency_overrides[get_job_service] = lambda: mock_service
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_job_dispatcher] = lambda: mock_dispatcher

    try:
        with pytest.raises(RuntimeError, match="Database commit failed"):
            await client.post(
                "/api/v1/jobs",
                json={"project_id": str(sample_job.project_id), "job_type": "REPORT_GENERATION"},
                headers={"Authorization": "Bearer admin.token"},
            )
        mock_dispatcher.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_get_job_dispatcher_returns_callable():
    """Verify that get_job_dispatcher returns the Celery delay callable."""
    from app.api.deps import get_job_dispatcher
    from app.tasks.jobs import process_job_task

    dispatcher = get_job_dispatcher()
    assert callable(dispatcher)
    assert dispatcher == process_job_task.delay
