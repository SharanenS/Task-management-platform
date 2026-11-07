from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_session
from app.main import app
from app.models import AttemptStatus, Job, JobAttempt, JobStatus, JobType
from app.service import Actor, get_dashboard_metrics


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as s:
        yield s


def make_actor(role: str = "MEMBER") -> Actor:
    return Actor(uuid4(), role)


def make_job(
    submitter_id: uuid4,
    status: JobStatus = JobStatus.SUBMITTED,
    created_at: datetime | None = None,
) -> Job:
    return Job(
        job_type=JobType.PROJECT_TASK_EXPORT,
        status=status,
        submitter_employee_id=submitter_id,
        payload={"format": "CSV", "includeCompleted": True, "projectId": str(uuid4())},
        request_fingerprint=uuid4().hex,
        idempotency_key=f"key-{uuid4().hex[:16]}",
        created_at=created_at or datetime.now(UTC),
    )


def test_empty_workspace_returns_zeros(session: Session) -> None:
    member = make_actor("MEMBER")
    data = get_dashboard_metrics(session, member)
    assert data.job_metrics.total_count == 0
    assert data.job_metrics.submitted_count == 0
    assert data.job_metrics.queued_count == 0
    assert data.job_metrics.running_count == 0
    assert data.job_metrics.succeeded_count == 0
    assert data.job_metrics.failed_count == 0
    assert data.job_metrics.cancelled_count == 0
    assert len(data.recent_jobs) == 0


def test_member_and_manager_scoped_to_own_jobs(session: Session) -> None:
    member = make_actor("MEMBER")
    manager = make_actor("MANAGER")
    other = make_actor("MEMBER")

    # Member jobs: 1 SUCCEEDED, 1 FAILED
    j1 = make_job(member.employee_id, JobStatus.SUCCEEDED)
    j2 = make_job(member.employee_id, JobStatus.FAILED)
    # Manager job: 1 RUNNING
    j3 = make_job(manager.employee_id, JobStatus.RUNNING)
    # Other user job: 1 SUBMITTED
    j4 = make_job(other.employee_id, JobStatus.SUBMITTED)

    session.add_all([j1, j2, j3, j4])
    session.commit()

    # Member sees only their 2 jobs
    member_data = get_dashboard_metrics(session, member)
    assert member_data.job_metrics.total_count == 2
    assert member_data.job_metrics.succeeded_count == 1
    assert member_data.job_metrics.failed_count == 1
    assert member_data.job_metrics.running_count == 0
    assert member_data.job_metrics.submitted_count == 0
    assert len(member_data.recent_jobs) == 2

    # Manager sees only their 1 job (manager status does NOT expose other users' jobs!)
    manager_data = get_dashboard_metrics(session, manager)
    assert manager_data.job_metrics.total_count == 1
    assert manager_data.job_metrics.running_count == 1
    assert manager_data.job_metrics.succeeded_count == 0
    assert len(manager_data.recent_jobs) == 1


def test_admin_metrics_covers_all_jobs(session: Session) -> None:
    admin = make_actor("ADMIN")
    u1 = make_actor("MEMBER")
    u2 = make_actor("MEMBER")

    j1 = make_job(u1.employee_id, JobStatus.QUEUED)
    j2 = make_job(u2.employee_id, JobStatus.CANCELLED)

    session.add_all([j1, j2])
    session.commit()

    admin_data = get_dashboard_metrics(session, admin)
    assert admin_data.job_metrics.total_count == 2
    assert admin_data.job_metrics.queued_count == 1
    assert admin_data.job_metrics.cancelled_count == 1
    assert len(admin_data.recent_jobs) == 2


def test_counts_logical_jobs_not_attempts(session: Session) -> None:
    """Prove that job metrics count logical jobs, not attempts or publication records."""
    member = make_actor("MEMBER")
    job = make_job(member.employee_id, JobStatus.RUNNING)
    session.add(job)
    session.flush()

    # Add 3 attempts to the job
    a1 = JobAttempt(job_id=job.id, attempt_number=1, status=AttemptStatus.FAILED)
    a2 = JobAttempt(job_id=job.id, attempt_number=2, status=AttemptStatus.FAILED)
    a3 = JobAttempt(job_id=job.id, attempt_number=3, status=AttemptStatus.RUNNING)
    session.add_all([a1, a2, a3])
    session.commit()

    data = get_dashboard_metrics(session, member)
    assert data.job_metrics.total_count == 1
    assert data.job_metrics.running_count == 1


def test_recent_jobs_bounded_and_deterministic_order(session: Session) -> None:
    member = make_actor("MEMBER")
    base_time = datetime.now(UTC)

    jobs = [
        make_job(
            member.employee_id, JobStatus.SUCCEEDED, created_at=base_time + timedelta(minutes=i)
        )
        for i in range(8)
    ]
    session.add_all(jobs)
    session.commit()

    data = get_dashboard_metrics(session, member)
    assert data.job_metrics.total_count == 8
    # Bounded to at most 5 recent jobs
    assert len(data.recent_jobs) == 5
    # Deterministic order: latest first
    created_times = [j.created_at for j in data.recent_jobs]
    assert created_times == sorted(created_times, reverse=True)


def test_query_count_does_not_grow_with_scale() -> None:
    """Prove that aggregate query count is O(1) and does not scale with job count."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    admin = make_actor("ADMIN")

    def seed(s: Session, count: int) -> None:
        for _ in range(count):
            s.add(make_job(admin.employee_id, JobStatus.SUCCEEDED))
        s.commit()

    # Small fixture: 2 jobs
    with Session(engine) as s:
        seed(s, 2)
        queries_small = 0

        def count_queries(conn, cursor, statement, parameters, context, executemany):
            nonlocal queries_small
            queries_small += 1

        event.listen(engine, "before_cursor_execute", count_queries)
        get_dashboard_metrics(s, admin)
        event.remove(engine, "before_cursor_execute", count_queries)

    # Large fixture: 50 jobs
    with Session(engine) as s:
        seed(s, 50)
        queries_large = 0

        def count_queries_large(conn, cursor, statement, parameters, context, executemany):
            nonlocal queries_large
            queries_large += 1

        event.listen(engine, "before_cursor_execute", count_queries_large)
        get_dashboard_metrics(s, admin)
        event.remove(engine, "before_cursor_execute", count_queries_large)

    assert queries_small == queries_large
    assert queries_small <= 3  # Exactly 2 queries (1 aggregate + 1 recent preview)


def test_api_internal_endpoint(session: Session) -> None:
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    admin = make_actor("ADMIN")

    j = make_job(admin.employee_id, JobStatus.SUCCEEDED)
    session.add(j)
    session.commit()

    response = client.get(
        "/internal/dashboard/metrics",
        headers={
            "X-Internal-Service-Key": settings.internal_service_key,
            "X-Actor-Employee-Id": str(admin.employee_id),
            "X-Actor-Application-Role": "ADMIN",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["job_metrics"]["total_count"] == 1
    assert payload["job_metrics"]["succeeded_count"] == 1
    assert len(payload["recent_jobs"]) == 1

    app.dependency_overrides.clear()
