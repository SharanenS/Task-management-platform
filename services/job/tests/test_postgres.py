import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import AttemptStatus, Job, JobAttempt, JobStatus
from app.schemas import JobSubmissionRequest
from app.service import Actor, JobError, claim_job, dispatch_job, settle_failure, submit_job

POSTGRES_URL = os.getenv("JOB_POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="Set JOB_POSTGRES_TEST_URL.")


def request(project_id: uuid.UUID, key: str) -> JobSubmissionRequest:
    return JobSubmissionRequest.model_validate(
        {
            "job_type": "PROJECT_TASK_EXPORT",
            "payload": {
                "project_id": str(project_id),
                "format": "CSV",
                "include_completed": True,
            },
            "idempotency_key": key,
        }
    )


@pytest.fixture
def factory() -> sessionmaker[Session]:
    assert POSTGRES_URL is not None
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    with engine.begin() as connection:
        connection.exec_driver_sql("TRUNCATE job_attempts, jobs CASCADE")
    return sessionmaker(engine, expire_on_commit=False)


def test_concurrent_identical_submission_creates_one_job(
    factory: sessionmaker[Session],
) -> None:
    current = Actor(uuid.uuid4(), "MEMBER")
    body = request(uuid.uuid4(), "phase6-postgres-identical")
    barrier = threading.Barrier(2)

    def submit() -> uuid.UUID:
        with factory() as session:
            barrier.wait()
            return submit_job(session, current, body).id

    with ThreadPoolExecutor(max_workers=2) as pool:
        identifiers = list(pool.map(lambda _: submit(), range(2)))
    assert identifiers[0] == identifiers[1]
    with factory() as session:
        assert len(list(session.scalars(select(Job)))) == 1


def test_concurrent_conflict_has_one_winner_and_one_sanitized_conflict(
    factory: sessionmaker[Session],
) -> None:
    current = Actor(uuid.uuid4(), "MEMBER")
    barrier = threading.Barrier(2)
    bodies = [
        request(uuid.uuid4(), "phase6-postgres-conflict"),
        request(uuid.uuid4(), "phase6-postgres-conflict"),
    ]

    def submit(body: JobSubmissionRequest) -> str:
        with factory() as session:
            barrier.wait()
            try:
                submit_job(session, current, body)
                return "created"
            except JobError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, bodies))
    assert sorted(results) == ["IDEMPOTENCY_CONFLICT", "created"]
    with factory() as session:
        jobs = list(session.scalars(select(Job)))
        assert len(jobs) == 1
        winner = jobs[0]
        winning_body = next(
            body for body in bodies if body.payload.project_id == winner.related_project_id
        )
        losing_body = next(body for body in bodies if body is not winning_body)
        assert submit_job(session, current, winning_body).id == winner.id
        with pytest.raises(JobError, match="idempotency key") as error:
            submit_job(session, current, losing_body)
        assert error.value.code == "IDEMPOTENCY_CONFLICT"
        assert len(list(session.scalars(select(Job)))) == 1


def test_different_actors_can_reuse_the_same_key(factory: sessionmaker[Session]) -> None:
    first = Actor(uuid.uuid4(), "MEMBER")
    second = Actor(uuid.uuid4(), "MEMBER")
    body = request(uuid.uuid4(), "phase6-postgres-shared-key")

    with factory() as session:
        first_job = submit_job(session, first, body)
    with factory() as session:
        second_job = submit_job(session, second, body)

    assert first_job.id != second_job.id
    with factory() as session:
        jobs = list(session.scalars(select(Job)))
        assert len(jobs) == 2
        assert {job.submitter_employee_id for job in jobs} == {
            first.employee_id,
            second.employee_id,
        }


def test_persistence_survives_new_engine_and_connection(factory: sessionmaker[Session]) -> None:
    current = Actor(uuid.uuid4(), "MEMBER")
    with factory() as session:
        job_id = submit_job(
            session,
            current,
            request(uuid.uuid4(), "phase6-postgres-persistence"),
        ).id
    assert POSTGRES_URL is not None
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    with Session(engine) as session:
        assert session.get(Job, job_id) is not None


class Publisher:
    def publish(self, _job_id: uuid.UUID) -> None:
        return None


def test_concurrent_dispatch_has_one_winner(factory: sessionmaker[Session]) -> None:
    current = Actor(uuid.uuid4(), "MEMBER")
    with factory() as session:
        job = submit_job(session, current, request(uuid.uuid4(), "phase7-postgres-dispatch"))
        job_id, version = job.id, job.version
    barrier = threading.Barrier(2)

    def dispatch() -> str:
        with factory() as session:
            barrier.wait()
            try:
                dispatch_job(session, current, job_id, version, Publisher())
                return "queued"
            except JobError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: dispatch(), range(2)))
    assert results.count("queued") == 1
    assert len(results) == 2 and results.count("queued") + results.count("VERSION_CONFLICT") == 2


def test_duplicate_delivery_creates_one_running_attempt(factory: sessionmaker[Session]) -> None:
    current = Actor(uuid.uuid4(), "MEMBER")
    with factory() as session:
        job = submit_job(session, current, request(uuid.uuid4(), "phase7-postgres-claim"))
        job_id = dispatch_job(session, current, job.id, job.version, Publisher()).id
    barrier = threading.Barrier(2)

    def claim() -> uuid.UUID | None:
        with factory() as session:
            barrier.wait()
            attempt = claim_job(session, job_id)
            return attempt.id if attempt else None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    assert sum(item is not None for item in results) == 1
    with factory() as session:
        assert len(list(session.scalars(select(JobAttempt)))) == 1


def test_retry_scheduled_status_persists_in_postgresql(factory: sessionmaker[Session]) -> None:
    current = Actor(uuid.uuid4(), "MEMBER")
    with factory() as session:
        job = submit_job(session, current, request(uuid.uuid4(), "phase7-postgres-retry"))
        job_id = dispatch_job(session, current, job.id, job.version, Publisher()).id
        attempt = claim_job(session, job_id)
        assert attempt is not None
        settle_failure(
            session,
            job_id,
            attempt.id,
            code="DEPENDENCY_UNAVAILABLE",
            retryable=True,
        )

    with factory() as session:
        persisted_job = session.get(Job, job_id)
        persisted_attempt = session.get(JobAttempt, attempt.id)
        assert persisted_job is not None and persisted_job.status == JobStatus.QUEUED
        assert persisted_attempt is not None
        assert persisted_attempt.status == AttemptStatus.RETRY_SCHEDULED
        assert persisted_attempt.failure_code == "DEPENDENCY_UNAVAILABLE"
