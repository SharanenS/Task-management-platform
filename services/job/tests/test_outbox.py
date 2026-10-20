import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Job, JobStatus, JobType, OutboxEvent, PublicationStatus
from app.service import (
    claim_publications,
    settle_publication_failure,
    settle_publication_success,
)


@pytest.fixture
def session() -> Generator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as value:
        yield value


def event(
    session: Session, *, status: PublicationStatus = PublicationStatus.PENDING
) -> OutboxEvent:
    job = Job(
        job_type=JobType.PROJECT_TASK_EXPORT,
        status=JobStatus.QUEUED,
        submitter_employee_id=uuid.uuid4(),
        related_project_id=uuid.uuid4(),
        payload={"projectId": str(uuid.uuid4()), "format": "CSV", "includeCompleted": True},
        request_fingerprint="a" * 64,
        idempotency_key=uuid.uuid4().hex,
    )
    value = OutboxEvent(job=job, status=status)
    session.add(value)
    session.commit()
    return value


def test_claim_and_exact_token_settlement(session: Session) -> None:
    value = event(session)
    claimed = claim_publications(session, now=datetime.now(UTC))
    assert [item.id for item in claimed] == [value.id]
    assert claimed[0].attempt_count == 1 and claimed[0].lease_token
    assert not settle_publication_success(session, value.id, "stale-token")
    assert settle_publication_success(session, value.id, claimed[0].lease_token or "")
    session.refresh(value)
    assert value.status == PublicationStatus.PUBLISHED and value.published_at
    assert claim_publications(session) == []


def test_failed_event_is_scheduled_and_reclaimed(session: Session) -> None:
    value = event(session)
    claimed = claim_publications(session)[0]
    first_token = claimed.lease_token
    assert settle_publication_failure(
        session, value.id, claimed.lease_token or "", "CONNECTION_FAILED"
    )
    session.refresh(value)
    assert value.status == PublicationStatus.FAILED
    assert value.last_failure_classification == "CONNECTION_FAILED"
    assert claim_publications(session, now=value.available_at - timedelta(milliseconds=1)) == []
    reclaimed = claim_publications(session, now=value.available_at)
    assert reclaimed[0].id == value.id and reclaimed[0].lease_token != first_token


def test_expired_claim_recovery_and_fresh_claim_protection(session: Session) -> None:
    value = event(session)
    start = datetime.now(UTC)
    first = claim_publications(session, lease_seconds=10, now=start)[0]
    old_token = first.lease_token
    assert claim_publications(session, now=start + timedelta(seconds=9)) == []
    second = claim_publications(session, now=start + timedelta(seconds=11))[0]
    assert second.lease_token != old_token
    assert not settle_publication_success(session, value.id, old_token or "")
