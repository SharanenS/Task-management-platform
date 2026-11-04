import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app import service as job_service
from app.models import (
    AttemptStatus,
    Job,
    JobAttempt,
    JobDomainEvent,
    JobStatus,
    OutboxEvent,
    PublicationStatus,
)
from app.schemas import JobSubmissionRequest
from app.service import (
    Actor,
    JobError,
    admin_retry_job,
    claim_job,
    claim_publications,
    dispatch_job,
    recover_expired_executions,
    settle_failure,
    settle_publication_failure,
    settle_publication_success,
    settle_success,
    submit_job,
)

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
        connection.exec_driver_sql(
            "TRUNCATE job_domain_outbox, job_publication_outbox, job_attempts, jobs CASCADE"
        )
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
    with factory() as session:
        assert len(list(session.scalars(select(OutboxEvent)))) == 1


def test_dispatch_and_outbox_are_atomic_and_unique(factory: sessionmaker[Session]) -> None:
    actor = Actor(uuid.uuid4(), "MEMBER")
    with factory() as session:
        job = submit_job(session, actor, request(uuid.uuid4(), "phase8-atomic-0001"))
        before = datetime.now(UTC)
        dispatched = dispatch_job(session, actor, job.id, job.version)
        after = datetime.now(UTC)
        events = list(session.scalars(select(OutboxEvent).where(OutboxEvent.job_id == job.id)))
        assert dispatched.status == JobStatus.QUEUED
        assert dispatched.execution_generation == 1
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "EXECUTE_JOB"
        assert event.schema_version == 1
        assert event.execution_generation == 1
        assert event.status == PublicationStatus.PENDING
        assert event.attempt_count == 0
        assert before <= event.available_at <= after
        assert event.lease_token is None and event.lease_expires_at is None
        assert [item.id for item in claim_publications(session, now=after)] == [event.id]
        assert event.status == PublicationStatus.IN_FLIGHT
        session.add(OutboxEvent(job_id=job.id, status=PublicationStatus.PENDING))
        with pytest.raises(IntegrityError):
            session.commit()


def test_dispatch_rolls_back_job_when_publication_insert_conflicts(
    factory: sessionmaker[Session],
) -> None:
    actor = Actor(uuid.uuid4(), "MEMBER")
    with factory() as session:
        job = submit_job(session, actor, request(uuid.uuid4(), "phase11-dispatch-rollback"))
        job_id, version = job.id, job.version
        session.add(
            OutboxEvent(
                job_id=job_id,
                event_type="EXECUTE_JOB",
                execution_generation=1,
                status=PublicationStatus.PENDING,
            )
        )
        session.commit()

    with factory() as session:
        with pytest.raises(JobError) as raised:
            dispatch_job(session, actor, job_id, version)
        assert raised.value.code == "JOB_NOT_DISPATCHABLE"

    with factory() as session:
        retained = session.get(Job, job_id)
        events = list(session.scalars(select(OutboxEvent).where(OutboxEvent.job_id == job_id)))
        assert retained is not None
        assert retained.status == JobStatus.SUBMITTED
        assert retained.execution_generation == 0
        assert retained.version == version
        assert len(events) == 1


def _pending(factory: sessionmaker[Session], key: str, created_at: datetime) -> uuid.UUID:
    actor = Actor(uuid.uuid4(), "MEMBER")
    with factory() as session:
        job = submit_job(session, actor, request(uuid.uuid4(), key))
        dispatch_job(session, actor, job.id, job.version)
        event = session.scalar(select(OutboxEvent).where(OutboxEvent.job_id == job.id))
        assert event is not None
        event.created_at = created_at
        session.commit()
        return event.id


def test_two_claimers_receive_disjoint_ordered_batches(factory: sessionmaker[Session]) -> None:
    base = datetime.now(UTC) - timedelta(minutes=1)
    identifiers = [
        _pending(factory, f"phase8-claim-000{index}", base + timedelta(seconds=index))
        for index in range(4)
    ]
    barrier = threading.Barrier(2)

    def claim() -> list[uuid.UUID]:
        with factory() as session:
            barrier.wait()
            return [item.id for item in claim_publications(session, batch_size=2)]

    with ThreadPoolExecutor(max_workers=2) as pool:
        batches = list(pool.map(lambda _: claim(), range(2)))
    assert not set(batches[0]).intersection(batches[1])
    assert set(batches[0] + batches[1]) == set(identifiers)
    assert identifiers[:2] in batches


def test_lease_reclaim_and_token_bound_settlement(factory: sessionmaker[Session]) -> None:
    event_id = _pending(factory, "phase8-lease-0001", datetime.now(UTC))
    start = datetime.now(UTC)
    with factory() as session:
        first = claim_publications(session, lease_seconds=10, now=start)[0]
        first_token = first.lease_token or ""
    with factory() as session:
        assert claim_publications(session, now=start + timedelta(seconds=9)) == []
    with factory() as session:
        second = claim_publications(session, now=start + timedelta(seconds=11))[0]
        second_token = second.lease_token or ""
        assert second_token != first_token
    with factory() as session:
        assert not settle_publication_success(session, event_id, first_token)
    with factory() as session:
        assert settle_publication_success(session, event_id, second_token)
        assert not settle_publication_success(session, event_id, second_token)
        assert claim_publications(session, now=start + timedelta(days=1)) == []


@pytest.mark.parametrize("classification", ["CONNECTION_FAILED", "CONFIRMATION_AMBIGUOUS"])
def test_failure_is_sanitized_scheduled_and_recoverable(
    factory: sessionmaker[Session], classification: str
) -> None:
    event_id = _pending(factory, f"phase8-failure-{classification}", datetime.now(UTC))
    with factory() as session:
        claimed = claim_publications(session)[0]
        assert settle_publication_failure(
            session, event_id, claimed.lease_token or "", classification
        )
        event = session.get(OutboxEvent, event_id)
        assert event is not None and event.status == PublicationStatus.FAILED
        assert event.last_failure_classification == classification
        eligible_at = event.available_at
    with factory() as session:
        assert claim_publications(session, now=eligible_at - timedelta(microseconds=1)) == []
        assert claim_publications(session, now=eligible_at)[0].id == event_id


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
            lease_token=attempt.execution_lease_token,
            execution_fence=attempt.execution_fence,
        )

    with factory() as session:
        persisted_job = session.get(Job, job_id)
        persisted_attempt = session.get(JobAttempt, attempt.id)
        assert persisted_job is not None and persisted_job.status == JobStatus.QUEUED
        assert persisted_attempt is not None
        assert persisted_attempt.status == AttemptStatus.RETRY_SCHEDULED
        assert persisted_attempt.failure_code == "DEPENDENCY_UNAVAILABLE"


def test_two_recovery_processes_claim_expired_execution_once(
    factory: sessionmaker[Session],
) -> None:
    actor = Actor(uuid.uuid4(), "MEMBER")
    start = datetime.now(UTC) - timedelta(minutes=1)
    with factory() as session:
        job = submit_job(session, actor, request(uuid.uuid4(), "phase9-recovery-once"))
        dispatch_job(session, actor, job.id, job.version)
        attempt = claim_job(session, job.id, now=start, lease_seconds=5)
        assert attempt
        job_id = job.id
    barrier = threading.Barrier(2)

    def recover() -> list[uuid.UUID]:
        with factory() as session:
            barrier.wait()
            return recover_expired_executions(session, now=datetime.now(UTC))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: recover(), range(2)))
    assert sum(job_id in result for result in results) == 1
    with factory() as session:
        assert len(list(session.scalars(select(OutboxEvent)))) == 2
        attempts = list(session.scalars(select(JobAttempt)))
        assert len(attempts) == 1 and attempts[0].status == AttemptStatus.ABANDONED


def test_stale_settlement_cannot_replace_recovered_generation(
    factory: sessionmaker[Session],
) -> None:
    actor = Actor(uuid.uuid4(), "MEMBER")
    start = datetime.now(UTC) - timedelta(minutes=1)
    with factory() as session:
        job = submit_job(session, actor, request(uuid.uuid4(), "phase9-stale-fence"))
        dispatch_job(session, actor, job.id, job.version)
        first = claim_job(session, job.id, now=start, lease_seconds=5)
        assert first
        stale = (first.id, first.execution_lease_token, first.execution_fence)
        recover_expired_executions(session, now=datetime.now(UTC))
        second = claim_job(session, job.id)
        assert second
        settle_success(
            session,
            job.id,
            second.id,
            content="reference,title\n",
            content_type="text/csv",
            checksum="b" * 64,
            row_count=0,
            truncated=False,
            lease_token=second.execution_lease_token,
            execution_fence=second.execution_fence,
        )
        with pytest.raises(JobError) as rejected:
            settle_success(
                session,
                job.id,
                stale[0],
                content="stale",
                content_type="text/plain",
                checksum="c" * 64,
                row_count=1,
                truncated=False,
                lease_token=stale[1],
                execution_fence=stale[2],
            )
        assert rejected.value.code == "STALE_SETTLEMENT"
        session.refresh(job)
        assert job.status == JobStatus.SUCCEEDED and job.result_checksum == "b" * 64
        events = list(
            session.scalars(select(JobDomainEvent).where(JobDomainEvent.job_id == job.id))
        )
        assert len(events) == 1 and events[0].event_type == "REPORT_SUCCEEDED"


def test_concurrent_admin_retry_creates_one_generation_event(
    factory: sessionmaker[Session],
) -> None:
    actor = Actor(uuid.uuid4(), "MEMBER")
    admin = Actor(uuid.uuid4(), "ADMIN")
    with factory() as session:
        job = submit_job(session, actor, request(uuid.uuid4(), "phase9-admin-race"))
        dispatch_job(session, actor, job.id, job.version)
        attempt = claim_job(session, job.id)
        assert attempt
        settle_failure(
            session,
            job.id,
            attempt.id,
            code="PERMANENT_FAILURE",
            retryable=False,
            lease_token=attempt.execution_lease_token,
            execution_fence=attempt.execution_fence,
        )
        session.refresh(job)
        job_id, version = job.id, job.version
    barrier = threading.Barrier(2)

    def retry() -> str:
        with factory() as session:
            barrier.wait()
            try:
                admin_retry_job(session, admin, job_id, version)
                return "queued"
            except JobError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: retry(), range(2)))
    assert results.count("queued") == 1
    assert any(value in {"VERSION_CONFLICT", "JOB_NOT_RETRYABLE"} for value in results)
    with factory() as session:
        assert len(list(session.scalars(select(OutboxEvent)))) == 2


def test_terminal_report_state_and_domain_event_commit_atomically(
    factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    actor = Actor(uuid.uuid4(), "MEMBER")
    with factory() as session:
        job = submit_job(session, actor, request(uuid.uuid4(), "phase11-terminal-atomic"))
        dispatch_job(session, actor, job.id, job.version)
        attempt = claim_job(session, job.id)
        assert attempt
        job_id, attempt_id = job.id, attempt.id
    with factory() as session:
        attempt = session.get(JobAttempt, attempt_id)
        assert attempt

        def fail_commit() -> None:
            raise RuntimeError("controlled terminal commit failure")

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="controlled terminal commit failure"):
            settle_success(
                session,
                job_id,
                attempt_id,
                content="reference,title\n",
                content_type="text/csv; charset=utf-8",
                checksum="d" * 64,
                row_count=0,
                truncated=False,
                lease_token=attempt.execution_lease_token,
                execution_fence=attempt.execution_fence,
            )
        session.rollback()
    with factory() as session:
        job = session.get(Job, job_id)
        assert job and job.status == JobStatus.RUNNING and job.result_content is None
        assert session.scalar(select(JobDomainEvent).where(JobDomainEvent.job_id == job_id)) is None


def test_terminal_event_uniqueness_failure_rolls_back_settlement(
    factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    actor = Actor(uuid.uuid4(), "MEMBER")
    with factory() as session:
        job = submit_job(session, actor, request(uuid.uuid4(), "phase11-terminal-unique-rollback"))
        dispatch_job(session, actor, job.id, job.version)
        attempt = claim_job(session, job.id)
        assert attempt
        job_id, attempt_id = job.id, attempt.id

    def add_conflicting_events(session: Session, job: Job, event_type: str) -> None:
        for _ in range(2):
            session.add(
                JobDomainEvent(
                    job_id=job.id,
                    event_type=event_type,
                    recipient_employee_id=job.submitter_employee_id,
                    project_id=job.related_project_id,
                )
            )

    monkeypatch.setattr(job_service, "_add_terminal_event", add_conflicting_events)
    with factory() as session:
        attempt = session.get(JobAttempt, attempt_id)
        assert attempt
        with pytest.raises(IntegrityError):
            settle_success(
                session,
                job_id,
                attempt_id,
                content="reference,title\n",
                content_type="text/csv; charset=utf-8",
                checksum="1" * 64,
                row_count=0,
                truncated=False,
                lease_token=attempt.execution_lease_token,
                execution_fence=attempt.execution_fence,
            )
        session.rollback()

    with factory() as session:
        job = session.get(Job, job_id)
        attempt = session.get(JobAttempt, attempt_id)
        assert job and attempt
        assert job.status == JobStatus.RUNNING
        assert attempt.status == AttemptStatus.RUNNING
        assert job.result_content is None
        assert job.result_content_type is None
        assert job.result_checksum is None
        assert job.result_row_count is None
        assert job.completed_at is None
        assert session.scalar(select(JobDomainEvent).where(JobDomainEvent.job_id == job_id)) is None


def test_terminal_report_event_is_unique_and_retry_is_nonterminal(
    factory: sessionmaker[Session],
) -> None:
    actor = Actor(uuid.uuid4(), "MEMBER")
    with factory() as session:
        job = submit_job(session, actor, request(uuid.uuid4(), "phase11-terminal-unique"))
        dispatch_job(session, actor, job.id, job.version)
        first = claim_job(session, job.id)
        assert first
        settle_failure(
            session,
            job.id,
            first.id,
            code="DEPENDENCY_UNAVAILABLE",
            retryable=True,
            lease_token=first.execution_lease_token,
            execution_fence=first.execution_fence,
        )
        assert session.scalar(select(JobDomainEvent).where(JobDomainEvent.job_id == job.id)) is None
        second = claim_job(session, job.id)
        assert second
        settle_success(
            session,
            job.id,
            second.id,
            content="reference,title\n",
            content_type="text/csv; charset=utf-8",
            checksum="e" * 64,
            row_count=0,
            truncated=False,
            lease_token=second.execution_lease_token,
            execution_fence=second.execution_fence,
        )
        events = list(
            session.scalars(select(JobDomainEvent).where(JobDomainEvent.job_id == job.id))
        )
        assert len(events) == 1 and events[0].event_type == "REPORT_SUCCEEDED"
        assert (
            job.result_checksum == "e" * 64 and job.result_content_type == "text/csv; charset=utf-8"
        )


def test_domain_event_cascade_is_owned_by_job(factory: sessionmaker[Session]) -> None:
    actor = Actor(uuid.uuid4(), "MEMBER")
    with factory() as session:
        jobs = [
            submit_job(session, actor, request(uuid.uuid4(), f"phase11-cascade-{index}"))
            for index in range(2)
        ]
        for job in jobs:
            dispatch_job(session, actor, job.id, job.version)
            attempt = claim_job(session, job.id)
            assert attempt
            settle_success(
                session,
                job.id,
                attempt.id,
                content="reference,title\n",
                content_type="text/csv; charset=utf-8",
                checksum="f" * 64,
                row_count=0,
                truncated=False,
                lease_token=attempt.execution_lease_token,
                execution_fence=attempt.execution_fence,
            )
        first_id, second_id = jobs[0].id, jobs[1].id
        session.delete(jobs[0])
        session.commit()
        assert (
            session.scalar(select(JobDomainEvent).where(JobDomainEvent.job_id == first_id)) is None
        )
        assert (
            session.scalar(select(JobDomainEvent).where(JobDomainEvent.job_id == second_id))
            is not None
        )
