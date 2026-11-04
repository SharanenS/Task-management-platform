import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from kombu.exceptions import OperationalError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import tasks
from app.db import Base
from app.execution import (
    ExecutionFailure,
    ExportResult,
    execute_project_task_export,
    render_csv,
    safe_cell,
)
from app.models import (
    AttemptStatus,
    DomainEventStatus,
    Job,
    JobAttempt,
    JobDomainEvent,
    JobStatus,
    OutboxEvent,
    PublicationStatus,
)
from app.publisher import QUEUE_NAME, ROUTING_KEY, TASK_NAME, CeleryPublisher, PublishFailure
from app.schemas import JobSubmissionRequest
from app.service import (
    Actor,
    JobError,
    claim_job,
    claim_publications,
    dispatch_job,
    settle_failure,
    settle_success,
    submit_job,
)


@pytest.fixture
def session() -> Generator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as value:
        yield value


def submitted(session: Session) -> tuple[Actor, Job]:
    actor = Actor(uuid.uuid4(), "MEMBER")
    body = JobSubmissionRequest.model_validate(
        {
            "job_type": "PROJECT_TASK_EXPORT",
            "payload": {
                "project_id": str(uuid.uuid4()),
                "format": "CSV",
                "include_completed": True,
            },
            "idempotency_key": "phase7-execution-test-0001",
        }
    )
    return actor, submit_job(session, actor, body)


class Publisher:
    def __init__(self) -> None:
        self.identifiers: list[uuid.UUID] = []

    def publish(self, job_id: uuid.UUID) -> None:
        self.identifiers.append(job_id)


def test_dispatch_creates_outbox_without_calling_publisher(session: Session) -> None:
    actor, job = submitted(session)
    publisher = Publisher()
    before = datetime.now(UTC)
    queued = dispatch_job(session, actor, job.id, job.version, publisher)
    after = datetime.now(UTC)
    assert queued.status == JobStatus.QUEUED
    assert queued.execution_generation == 1
    assert queued.version == 2
    assert publisher.identifiers == []
    event = session.query(OutboxEvent).one()
    assert event.job_id == job.id
    assert event.event_type == "EXECUTE_JOB"
    assert event.schema_version == 1
    assert event.execution_generation == 1
    assert event.status == PublicationStatus.PENDING
    assert event.attempt_count == 0
    available_at = event.available_at.replace(tzinfo=event.available_at.tzinfo or UTC)
    assert before <= available_at <= after
    assert event.lease_token is None and event.lease_expires_at is None
    assert event.published_at is None and event.last_failure_classification is None
    claimed = claim_publications(session, now=after)
    assert [item.id for item in claimed] == [event.id]
    assert claimed[0].status == PublicationStatus.IN_FLIGHT


def test_dispatch_requires_owner_or_admin_and_exact_version(session: Session) -> None:
    actor, job = submitted(session)
    with pytest.raises(JobError) as concealed:
        dispatch_job(session, Actor(uuid.uuid4(), "MEMBER"), job.id, job.version, Publisher())
    assert concealed.value.code == "JOB_NOT_FOUND"
    with pytest.raises(JobError) as stale:
        dispatch_job(session, actor, job.id, 999, Publisher())
    assert stale.value.code == "VERSION_CONFLICT"


def test_claim_is_idempotent_for_duplicate_delivery(session: Session) -> None:
    actor, job = submitted(session)
    dispatch_job(session, actor, job.id, job.version, Publisher())
    attempt = claim_job(session, job.id)
    assert attempt and attempt.status == AttemptStatus.RUNNING
    assert claim_job(session, job.id) is None


def test_success_settles_attempt_and_result_atomically(session: Session) -> None:
    actor, job = submitted(session)
    dispatch_job(session, actor, job.id, job.version, Publisher())
    attempt = claim_job(session, job.id)
    assert attempt
    settle_success(
        session,
        job.id,
        attempt.id,
        content="reference,title\nT-1,Safe\n",
        content_type="text/csv; charset=utf-8",
        checksum="a" * 64,
        row_count=1,
        truncated=False,
        lease_token=attempt.execution_lease_token,
        execution_fence=attempt.execution_fence,
    )
    session.refresh(job)
    session.refresh(attempt)
    assert (job.status, attempt.status) == (JobStatus.SUCCEEDED, AttemptStatus.SUCCEEDED)
    assert job.result_row_count == 1 and job.completed_at is not None


def test_celery_task_commits_report_result_and_terminal_event_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    actor = Actor(uuid.uuid4(), "MEMBER")
    project_id = uuid.uuid4()
    body = JobSubmissionRequest.model_validate(
        {
            "job_type": "PROJECT_TASK_EXPORT",
            "payload": {
                "project_id": str(project_id),
                "format": "CSV",
                "include_completed": True,
            },
            "idempotency_key": "phase11-worker-boundary-0001",
        }
    )
    with sessions() as setup:
        job = submit_job(setup, actor, body)
        dispatch_job(setup, actor, job.id, job.version)
        job_id = job.id

    content = "reference,title\nT-1,Safe report\n"
    result = ExportResult(
        content=content,
        content_type="text/csv; charset=utf-8",
        checksum="a" * 64,
        row_count=1,
        truncated=False,
    )
    monkeypatch.setattr(tasks, "SessionLocal", sessions)
    monkeypatch.setattr(tasks, "execute_project_task_export", lambda *_args: result)

    tasks.execute_job.run(str(job_id))
    tasks.execute_job.run(str(job_id))

    with sessions() as verification:
        job = verification.get(Job, job_id)
        assert job
        attempts = verification.query(JobAttempt).filter_by(job_id=job_id).all()
        events = verification.query(JobDomainEvent).filter_by(job_id=job_id).all()
        assert job.status == JobStatus.SUCCEEDED
        assert job.result_content == content
        assert job.result_content_type == "text/csv; charset=utf-8"
        assert job.result_checksum == "a" * 64
        assert job.result_row_count == 1
        assert job.result_truncated is False
        assert len(attempts) == 1 and attempts[0].status == AttemptStatus.SUCCEEDED
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "REPORT_SUCCEEDED"
        assert event.job_id == job_id
        assert event.recipient_employee_id == actor.employee_id
        assert event.project_id == project_id
        assert event.schema_version == 1
        assert event.status == DomainEventStatus.PENDING
        assert event.attempt_count == 0
        available_at = event.available_at.replace(tzinfo=event.available_at.tzinfo or UTC)
        assert available_at <= datetime.now(UTC)
        assert event.lease_token is None and event.lease_expires_at is None
        assert event.published_at is None
        assert event.last_failure_classification is None


def test_transient_failure_schedules_retry_then_terminal_failure(session: Session) -> None:
    actor, job = submitted(session)
    dispatch_job(session, actor, job.id, job.version, Publisher())
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
    session.refresh(job)
    session.refresh(first)
    assert (job.status, first.status) == (JobStatus.QUEUED, AttemptStatus.RETRY_SCHEDULED)
    second = claim_job(session, job.id)
    assert second and second.attempt_number == 2
    settle_failure(
        session,
        job.id,
        second.id,
        code="DEPENDENCY_UNAVAILABLE",
        retryable=True,
        retry_exhausted=True,
        lease_token=second.execution_lease_token,
        execution_fence=second.execution_fence,
    )
    session.refresh(job)
    assert job.status == JobStatus.FAILED
    assert job.failure_classification == "DEPENDENCY_UNAVAILABLE"
    event = session.query(JobDomainEvent).one()
    assert event.event_type == "REPORT_FAILED"
    assert event.job_id == job.id
    assert event.recipient_employee_id == actor.employee_id
    assert event.project_id == job.related_project_id


@pytest.mark.parametrize("value", ["=1+1", "+cmd", "-2", "@link", "\tvalue", "\rvalue"])
def test_csv_formula_prefixes_are_neutralized(value: str) -> None:
    assert safe_cell(value).startswith("'")


def test_csv_is_well_formed_bounded_and_checksumed() -> None:
    result = render_csv(
        [
            {
                "reference": "PRJ-1",
                "title": 'comma, quote " newline\nvalue',
                "status": "TODO",
                "priority": "HIGH",
                "assigneeDisplayName": "Person",
                "dueDate": None,
            }
        ],
        truncated=False,
    )
    assert '"comma, quote "" newline\nvalue"' in result.content
    assert result.row_count == 1 and len(result.checksum) == 64


def test_execution_reloads_submitter_and_project_access(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def get(url: str, **_: object) -> object:
        calls.append(url)
        if "employees" in url:
            return {"active": True, "role": "MEMBER"}
        return {"items": [], "truncated": False}

    monkeypatch.setattr("app.execution._get", get)
    project_id = uuid.uuid4()
    result = execute_project_task_export(
        uuid.uuid4(), {"projectId": str(project_id), "includeCompleted": True}
    )
    assert result.row_count == 0
    assert len(calls) == 2 and str(project_id) in calls[1]


def test_inactive_submitter_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.execution._get", lambda *_args, **_kwargs: {"active": False})
    with pytest.raises(ExecutionFailure) as raised:
        execute_project_task_export(
            uuid.uuid4(), {"projectId": str(uuid.uuid4()), "includeCompleted": True}
        )
    assert (raised.value.code, raised.value.retryable) == ("SUBMITTER_INACTIVE", False)
    assert "password" not in str(raised.value).lower()


class CeleryStub:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.calls: list[tuple[str, dict[str, object]]] = []

    def send_task(self, name: str, **values: object) -> None:
        self.calls.append((name, values))
        if self.failure:
            raise self.failure


def test_celery_publisher_sends_only_job_identifier_with_confirms() -> None:
    celery = CeleryStub()
    identifier = uuid.uuid4()
    CeleryPublisher(celery).publish(identifier)  # type: ignore[arg-type]
    assert celery.calls == [
        (
            TASK_NAME,
            {
                "args": [str(identifier)],
                "queue": QUEUE_NAME,
                "routing_key": ROUTING_KEY,
                "serializer": "json",
                "retry": False,
                "delivery_mode": 2,
                "confirm_publish": True,
            },
        )
    ]


@pytest.mark.parametrize(
    ("failure", "ambiguous"),
    [(OperationalError("connection"), False), (TimeoutError("confirmation"), True)],
)
def test_celery_publisher_classifies_failures_without_details(
    failure: Exception, ambiguous: bool
) -> None:
    with pytest.raises(PublishFailure) as raised:
        CeleryPublisher(CeleryStub(failure)).publish(uuid.uuid4())  # type: ignore[arg-type]
    assert raised.value.ambiguous is ambiguous
    assert str(raised.value) == "Job publication failed."
    assert str(failure) not in str(raised.value)
