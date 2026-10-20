import uuid
from collections.abc import Generator

import pytest
from kombu.exceptions import OperationalError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.execution import (
    ExecutionFailure,
    execute_project_task_export,
    render_csv,
    safe_cell,
)
from app.models import AttemptStatus, Job, JobStatus
from app.publisher import QUEUE_NAME, ROUTING_KEY, TASK_NAME, CeleryPublisher
from app.schemas import JobSubmissionRequest
from app.service import (
    Actor,
    JobError,
    PublishFailure,
    claim_job,
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
    def __init__(self, failure: PublishFailure | None = None) -> None:
        self.failure = failure
        self.identifiers: list[uuid.UUID] = []

    def publish(self, job_id: uuid.UUID) -> None:
        self.identifiers.append(job_id)
        if self.failure:
            raise self.failure


def test_dispatch_publishes_only_identifier_and_queues(session: Session) -> None:
    actor, job = submitted(session)
    publisher = Publisher()
    queued = dispatch_job(session, actor, job.id, job.version, publisher)
    assert queued.status == JobStatus.QUEUED
    assert queued.version == 2
    assert publisher.identifiers == [job.id]


def test_dispatch_requires_owner_or_admin_and_exact_version(session: Session) -> None:
    actor, job = submitted(session)
    with pytest.raises(JobError) as concealed:
        dispatch_job(session, Actor(uuid.uuid4(), "MEMBER"), job.id, job.version, Publisher())
    assert concealed.value.code == "JOB_NOT_FOUND"
    with pytest.raises(JobError) as stale:
        dispatch_job(session, actor, job.id, 999, Publisher())
    assert stale.value.code == "VERSION_CONFLICT"


def test_unambiguous_publish_failure_compensates_to_submitted(session: Session) -> None:
    actor, job = submitted(session)
    with pytest.raises(JobError) as raised:
        dispatch_job(
            session, actor, job.id, job.version, Publisher(PublishFailure(ambiguous=False))
        )
    session.refresh(job)
    assert raised.value.code == "BROKER_UNAVAILABLE"
    assert job.status == JobStatus.SUBMITTED


def test_ambiguous_publish_failure_leaves_queued_for_manual_resolution(session: Session) -> None:
    actor, job = submitted(session)
    with pytest.raises(JobError):
        dispatch_job(session, actor, job.id, job.version, Publisher(PublishFailure(ambiguous=True)))
    session.refresh(job)
    assert job.status == JobStatus.QUEUED


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
    )
    session.refresh(job)
    session.refresh(attempt)
    assert (job.status, attempt.status) == (JobStatus.SUCCEEDED, AttemptStatus.SUCCEEDED)
    assert job.result_row_count == 1 and job.completed_at is not None


def test_transient_failure_schedules_retry_then_terminal_failure(session: Session) -> None:
    actor, job = submitted(session)
    dispatch_job(session, actor, job.id, job.version, Publisher())
    first = claim_job(session, job.id)
    assert first
    settle_failure(session, job.id, first.id, code="DEPENDENCY_UNAVAILABLE", retryable=True)
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
    )
    session.refresh(job)
    assert job.status == JobStatus.FAILED
    assert job.failure_classification == "DEPENDENCY_UNAVAILABLE"


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
