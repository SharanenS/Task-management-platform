import uuid
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_session
from app.main import app


def client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def session_override() -> Generator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    return TestClient(app)


def headers(employee_id: uuid.UUID | None = None, role: str = "MEMBER") -> dict[str, str]:
    return {
        "X-Internal-Service-Key": settings.internal_service_key,
        "X-Actor-Employee-Id": str(employee_id or uuid.uuid4()),
        "X-Actor-Application-Role": role,
    }


def test_internal_auth_and_actor_context_fail_closed() -> None:
    api = client()
    assert api.get("/internal/jobs").status_code == 403
    assert (
        api.get(
            "/internal/jobs", headers={"X-Internal-Service-Key": settings.internal_service_key}
        ).status_code
        == 403
    )


def test_submit_list_detail_and_empty_attempts() -> None:
    api = client()
    actor_headers = headers()
    response = api.post(
        "/internal/jobs",
        headers=actor_headers,
        json={
            "job_type": "PROJECT_TASK_EXPORT",
            "payload": {
                "project_id": str(uuid.uuid4()),
                "format": "CSV",
                "include_completed": True,
            },
            "idempotency_key": "phase6-api-key-0001",
        },
    )
    assert response.status_code == 200
    job = response.json()
    assert job["status"] == "SUBMITTED"
    assert api.get("/internal/jobs", headers=actor_headers).json()["items"][0]["id"] == job["id"]
    assert api.get(f"/internal/jobs/{job['id']}", headers=actor_headers).status_code == 200
    assert (
        api.get(f"/internal/jobs/{job['id']}/attempts", headers=actor_headers).json()["items"] == []
    )


def test_dispatch_endpoint_enforces_owner_version_and_state() -> None:
    api = client()
    actor_headers = headers()
    submitted = api.post(
        "/internal/jobs",
        headers=actor_headers,
        json={
            "job_type": "PROJECT_TASK_EXPORT",
            "payload": {
                "project_id": str(uuid.uuid4()),
                "format": "CSV",
                "include_completed": True,
            },
            "idempotency_key": "phase7-api-dispatch-0001",
        },
    ).json()

    denied = api.post(
        f"/internal/jobs/{submitted['id']}/dispatch",
        headers=headers(),
        json={"expected_version": submitted["version"]},
    )
    assert denied.status_code == 404 and denied.json()["detail"]["code"] == "JOB_NOT_FOUND"
    queued = api.post(
        f"/internal/jobs/{submitted['id']}/dispatch",
        headers=actor_headers,
        json={"expected_version": submitted["version"]},
    )
    assert queued.status_code == 200 and queued.json()["status"] == "QUEUED"
    repeated = api.post(
        f"/internal/jobs/{submitted['id']}/dispatch",
        headers=actor_headers,
        json={"expected_version": queued.json()["version"]},
    )
    assert repeated.status_code == 409
    assert repeated.json()["detail"]["code"] == "JOB_NOT_DISPATCHABLE"
