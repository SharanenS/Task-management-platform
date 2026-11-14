import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Job, JobStatus, JobType
from app.schemas import JobSubmissionRequest
from app.service import (
    Actor,
    JobError,
    ensure_transition,
    get_job,
    list_attempts,
    list_jobs,
    normalize_request,
    submit_job,
)


@pytest.fixture
def session() -> Generator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as value:
        yield value


def actor(role: str = "MEMBER") -> Actor:
    return Actor(uuid.uuid4(), role)


def request(
    key: str = "phase6-test-key-0001", project_id: uuid.UUID | None = None
) -> JobSubmissionRequest:
    return JobSubmissionRequest.model_validate(
        {
            "job_type": "PROJECT_TASK_EXPORT",
            "payload": {
                "project_id": str(project_id or uuid.uuid4()),
                "format": "CSV",
                "include_completed": True,
            },
            "idempotency_key": key,
        }
    )


def test_payload_normalizes_and_fingerprints_deterministically() -> None:
    value = request()
    payload, first = normalize_request(value)
    _, second = normalize_request(value)
    assert payload == {
        "format": "CSV",
        "includeCompleted": True,
        "projectId": str(value.payload.project_id),
    }
    assert first == second and len(first) == 64


@pytest.mark.parametrize(
    "change",
    [
        {"job_type": "COMMAND"},
        {"extra": "curl https://internal"},
        {"payload": {"project_id": str(uuid.uuid4()), "script": "echo secret"}},
        {"idempotency_key": "short"},
    ],
)
def test_payload_rejects_unsupported_unknown_and_invalid_values(change: dict[str, object]) -> None:
    data = request().model_dump(mode="json")
    data.update(change)
    with pytest.raises(ValidationError):
        JobSubmissionRequest.model_validate(data)


def test_submission_is_initially_submitted_with_no_attempts(session: Session) -> None:
    current = actor()
    job = submit_job(session, current, request())
    assert job.status == JobStatus.SUBMITTED
    assert job.submitter_employee_id == current.employee_id
    assert list_attempts(session, current, job.id) == []
    assert job.result_summary is None and job.failure_classification is None


def test_identical_replay_returns_same_job(session: Session) -> None:
    current = actor()
    body = request()
    assert submit_job(session, current, body).id == submit_job(session, current, body).id
    assert len(list(session.scalars(select(Job)))) == 1


def test_conflicting_replay_is_sanitized(session: Session) -> None:
    current = actor()
    submit_job(session, current, request(project_id=uuid.uuid4()))
    with pytest.raises(JobError, match="already in use") as raised:
        submit_job(session, current, request(project_id=uuid.uuid4()))
    assert raised.value.code == "IDEMPOTENCY_CONFLICT"


def test_same_key_is_scoped_by_actor(session: Session) -> None:
    first, second = actor(), actor()
    body = request()
    assert submit_job(session, first, body).id != submit_job(session, second, body).id


def test_owner_visibility_and_admin_directory(session: Session) -> None:
    first, second = actor(), actor()
    first_job = submit_job(session, first, request("phase6-test-key-0002"))
    submit_job(session, second, request("phase6-test-key-0002"))
    assert [item.id for item in list_jobs(session, first).items] == [first_job.id]
    admin = Actor(uuid.uuid4(), "ADMIN")
    assert len(list_jobs(session, admin).items) == 2


def test_inaccessible_detail_is_concealed(session: Session) -> None:
    job = submit_job(session, actor(), request())
    with pytest.raises(JobError) as raised:
        get_job(session, actor(), job.id)
    assert (raised.value.code, raised.value.status_code) == ("JOB_NOT_FOUND", 404)


def test_filters_and_forward_cursor_are_stable(session: Session) -> None:
    current = actor()
    moment = datetime(2026, 10, 16, tzinfo=UTC)
    for index in range(3):
        job = submit_job(session, current, request(f"phase6-test-key-000{index + 3}"))
        job.created_at = moment
    session.commit()
    first = list_jobs(
        session, current, first=2, status=JobStatus.SUBMITTED, job_type=JobType.PROJECT_TASK_EXPORT
    )
    second = list_jobs(session, current, first=2, after=first.next_cursor)
    assert first.has_next_page and len(first.items) == 2
    assert len(second.items) == 1
    assert {item.id for item in first.items}.isdisjoint(item.id for item in second.items)


@pytest.mark.parametrize("size", [0, 51])
def test_page_size_is_bounded(session: Session, size: int) -> None:
    with pytest.raises(JobError, match="between 1 and 50"):
        list_jobs(session, actor(), first=size)


def test_malformed_cursor_is_rejected(session: Session) -> None:
    with pytest.raises(JobError) as raised:
        list_jobs(session, actor(), after="not-a-cursor")
    assert raised.value.code == "INVALID_CURSOR"


def test_future_state_machine_is_defined_without_execution() -> None:
    ensure_transition(JobStatus.SUBMITTED, JobStatus.QUEUED)
    ensure_transition(JobStatus.RUNNING, JobStatus.SUCCEEDED)
    with pytest.raises(JobError):
        ensure_transition(JobStatus.SUBMITTED, JobStatus.SUCCEEDED)
    with pytest.raises(JobError):
        ensure_transition(JobStatus.SUCCEEDED, JobStatus.RUNNING)
