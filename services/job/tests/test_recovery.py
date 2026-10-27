import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import AttemptStatus, Job, JobAttempt, JobStatus, OutboxEvent
from app.schemas import JobSubmissionRequest
from app.service import (
    Actor,
    JobError,
    admin_retry_job,
    claim_job,
    dispatch_job,
    heartbeat_execution,
    recover_expired_executions,
    settle_failure,
    settle_success,
    submit_job,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as value:
        yield value


def queued(session: Session) -> tuple[Actor, Job]:
    actor = Actor(uuid.uuid4(), "MEMBER")
    body = JobSubmissionRequest.model_validate(
        {
            "job_type": "PROJECT_TASK_EXPORT",
            "payload": {"project_id": str(uuid.uuid4()), "format": "CSV"},
            "idempotency_key": f"phase9-{uuid.uuid4().hex}",
        }
    )
    job = submit_job(session, actor, body)
    return actor, dispatch_job(session, actor, job.id, job.version)


def test_current_owner_heartbeats_and_stale_owner_is_rejected(session: Session) -> None:
    _, job = queued(session)
    start = datetime.now(UTC)
    attempt = claim_job(session, job.id, now=start, lease_seconds=20)
    assert attempt and heartbeat_execution(
        session,
        attempt.id,
        attempt.execution_lease_token or "",
        attempt.execution_fence,
        now=start + timedelta(seconds=5),
    )
    assert not heartbeat_execution(
        session, attempt.id, "stale", attempt.execution_fence, now=start + timedelta(seconds=6)
    )


def test_expired_execution_recovers_once_and_fences_stale_settlement(session: Session) -> None:
    _, job = queued(session)
    start = datetime.now(UTC)
    first = claim_job(session, job.id, now=start, lease_seconds=5)
    assert first
    token, fence = first.execution_lease_token, first.execution_fence
    assert recover_expired_executions(session, now=start + timedelta(seconds=4)) == []
    assert recover_expired_executions(session, now=start + timedelta(seconds=6)) == [job.id]
    assert recover_expired_executions(session, now=start + timedelta(seconds=6)) == []
    session.refresh(first)
    session.refresh(job)
    assert first.status == AttemptStatus.ABANDONED and job.status == JobStatus.QUEUED
    assert len(list(session.scalars(select(OutboxEvent).where(OutboxEvent.job_id == job.id)))) == 2
    second = claim_job(session, job.id, now=start + timedelta(seconds=7))
    assert second and second.execution_fence > fence
    with pytest.raises(JobError, match="no longer active"):
        settle_success(
            session,
            job.id,
            first.id,
            content="stale",
            content_type="text/plain",
            checksum="a" * 64,
            row_count=1,
            truncated=False,
            lease_token=token,
            execution_fence=fence,
        )


def test_retry_policy_is_bounded_and_admin_retry_is_single_use(session: Session) -> None:
    _, job = queued(session)
    for number in range(1, 4):
        attempt = claim_job(session, job.id)
        assert attempt and attempt.attempt_number == number
        settle_failure(
            session,
            job.id,
            attempt.id,
            code="DEPENDENCY_UNAVAILABLE",
            retryable=True,
            lease_token=attempt.execution_lease_token,
            execution_fence=attempt.execution_fence,
        )
    session.refresh(job)
    assert job.status == JobStatus.FAILED and job.retry_exhausted
    admin = Actor(uuid.uuid4(), "ADMIN")
    retried = admin_retry_job(session, admin, job.id, job.version)
    assert retried.status == JobStatus.QUEUED and retried.manual_retry_count == 1
    with pytest.raises(JobError) as denied:
        admin_retry_job(session, Actor(uuid.uuid4(), "MANAGER"), job.id, job.version)
    assert denied.value.code == "FORBIDDEN"


def test_duplicate_delivery_does_not_replace_active_owner(session: Session) -> None:
    _, job = queued(session)
    first = claim_job(session, job.id)
    assert first and claim_job(session, job.id) is None
    assert len(list(session.scalars(select(JobAttempt)))) == 1
