import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AttemptStatus, Job, JobAttempt, JobStatus, JobType
from app.schemas import JobSubmissionRequest

MAX_PAYLOAD_BYTES = 1024
TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.SUBMITTED: frozenset({JobStatus.QUEUED, JobStatus.CANCELLED}),
    JobStatus.QUEUED: frozenset({JobStatus.RUNNING, JobStatus.CANCELLED}),
    JobStatus.RUNNING: frozenset({JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}),
    JobStatus.SUCCEEDED: frozenset(),
    JobStatus.FAILED: frozenset(),
    JobStatus.CANCELLED: frozenset(),
}


@dataclass(frozen=True)
class Actor:
    employee_id: UUID
    application_role: str


@dataclass(frozen=True)
class Page:
    items: list[Job]
    next_cursor: str | None
    has_next_page: bool


class JobError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class Publisher(Protocol):
    def publish(self, job_id: UUID) -> None: ...


class PublishFailure(Exception):
    def __init__(self, *, ambiguous: bool = False) -> None:
        super().__init__("Job publication failed.")
        self.ambiguous = ambiguous


def normalize_request(body: JobSubmissionRequest) -> tuple[dict[str, object], str]:
    payload = {
        "format": body.payload.format,
        "includeCompleted": body.payload.include_completed,
        "projectId": str(body.payload.project_id),
    }
    canonical = json.dumps(
        {"jobType": body.job_type.value, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if len(canonical) > MAX_PAYLOAD_BYTES:
        raise JobError("INVALID_INPUT", "The job payload is too large.")
    return payload, hashlib.sha256(canonical).hexdigest()


def ensure_transition(current: JobStatus, target: JobStatus) -> None:
    if target not in TRANSITIONS[current]:
        raise JobError("INVALID_JOB_TRANSITION", "The requested job transition is invalid.")


def submit_job(session: Session, actor: Actor, body: JobSubmissionRequest) -> Job:
    payload, fingerprint = normalize_request(body)
    existing = session.scalar(
        select(Job).where(
            Job.submitter_employee_id == actor.employee_id,
            Job.idempotency_key == body.idempotency_key,
        )
    )
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise JobError("IDEMPOTENCY_CONFLICT", "The idempotency key is already in use.", 409)
        return existing
    job = Job(
        job_type=JobType.PROJECT_TASK_EXPORT,
        status=JobStatus.SUBMITTED,
        submitter_employee_id=actor.employee_id,
        related_project_id=body.payload.project_id,
        payload=payload,
        request_fingerprint=fingerprint,
        idempotency_key=body.idempotency_key,
    )
    session.add(job)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        winner = session.scalar(
            select(Job).where(
                Job.submitter_employee_id == actor.employee_id,
                Job.idempotency_key == body.idempotency_key,
            )
        )
        if winner is None:
            raise JobError("SUBMISSION_FAILED", "The job could not be submitted.", 503) from None
        if winner.request_fingerprint != fingerprint:
            raise JobError(
                "IDEMPOTENCY_CONFLICT", "The idempotency key is already in use.", 409
            ) from None
        return winner
    session.refresh(job)
    return job


def _cursor(job: Job) -> str:
    value = json.dumps([job.created_at.isoformat(), str(job.id)], separators=(",", ":"))
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def _decode_cursor(value: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        parts = json.loads(raw)
        if not isinstance(parts, list) or len(parts) != 2:
            raise ValueError
        return datetime.fromisoformat(parts[0]), UUID(parts[1])
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise JobError("INVALID_CURSOR", "The job cursor is invalid.") from error


def list_jobs(
    session: Session,
    actor: Actor,
    *,
    first: int = 20,
    after: str | None = None,
    status: JobStatus | None = None,
    job_type: JobType | None = None,
) -> Page:
    if first < 1 or first > 50:
        raise JobError("INVALID_PAGE_SIZE", "The page size must be between 1 and 50.")
    statement = select(Job)
    if actor.application_role != "ADMIN":
        statement = statement.where(Job.submitter_employee_id == actor.employee_id)
    if status:
        statement = statement.where(Job.status == status)
    if job_type:
        statement = statement.where(Job.job_type == job_type)
    if after:
        created_at, job_id = _decode_cursor(after)
        statement = statement.where(
            or_(Job.created_at < created_at, and_(Job.created_at == created_at, Job.id < job_id))
        )
    items = list(
        session.scalars(statement.order_by(Job.created_at.desc(), Job.id.desc()).limit(first + 1))
    )
    has_next_page = len(items) > first
    items = items[:first]
    return Page(items, _cursor(items[-1]) if has_next_page else None, has_next_page)


def get_job(session: Session, actor: Actor, job_id: UUID) -> Job:
    job = session.get(Job, job_id)
    if job is None or (
        actor.application_role != "ADMIN" and job.submitter_employee_id != actor.employee_id
    ):
        raise JobError("JOB_NOT_FOUND", "The job was not found.", 404)
    return job


def list_attempts(session: Session, actor: Actor, job_id: UUID) -> list[JobAttempt]:
    get_job(session, actor, job_id)
    return list(
        session.scalars(
            select(JobAttempt)
            .where(JobAttempt.job_id == job_id)
            .order_by(JobAttempt.attempt_number, JobAttempt.id)
        )
    )


def dispatch_job(
    session: Session,
    actor: Actor,
    job_id: UUID,
    expected_version: int,
    publisher: Publisher,
) -> Job:
    job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if job is None or (
        actor.application_role != "ADMIN" and job.submitter_employee_id != actor.employee_id
    ):
        raise JobError("JOB_NOT_FOUND", "The job was not found.", 404)
    if job.version != expected_version:
        raise JobError("VERSION_CONFLICT", "The job changed before it could be dispatched.", 409)
    if job.status != JobStatus.SUBMITTED:
        raise JobError(
            "JOB_NOT_DISPATCHABLE", "The job cannot be dispatched in its current state.", 409
        )
    job.status = JobStatus.QUEUED
    job.version += 1
    queued_version = job.version
    session.commit()
    session.refresh(job)
    try:
        publisher.publish(job.id)
    except PublishFailure as error:
        if not error.ambiguous:
            current = session.scalar(select(Job).where(Job.id == job.id).with_for_update())
            if current and current.status == JobStatus.QUEUED and current.version == queued_version:
                current.status = JobStatus.SUBMITTED
                current.version += 1
                session.commit()
        raise JobError(
            "BROKER_UNAVAILABLE", "Job dispatch is temporarily unavailable.", 503
        ) from None
    return job


def claim_job(session: Session, job_id: UUID) -> JobAttempt | None:
    job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if job is None or job.status != JobStatus.QUEUED:
        return None
    attempt_number = len(job.attempts) + 1
    attempt = JobAttempt(
        job_id=job.id,
        attempt_number=attempt_number,
        status=AttemptStatus.RUNNING,
        retryable=False,
    )
    job.status = JobStatus.RUNNING
    job.version += 1
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return attempt


def settle_success(
    session: Session,
    job_id: UUID,
    attempt_id: UUID,
    *,
    content: str,
    content_type: str,
    checksum: str,
    row_count: int,
    truncated: bool,
) -> None:
    job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    attempt = session.scalar(
        select(JobAttempt)
        .where(JobAttempt.id == attempt_id, JobAttempt.job_id == job_id)
        .with_for_update()
    )
    if (
        not job
        or not attempt
        or job.status != JobStatus.RUNNING
        or attempt.status != AttemptStatus.RUNNING
    ):
        raise JobError("STALE_SETTLEMENT", "The execution attempt is no longer active.", 409)
    now = datetime.now(UTC)
    attempt.status = AttemptStatus.SUCCEEDED
    attempt.finished_at = now
    job.status = JobStatus.SUCCEEDED
    job.result_content = content
    job.result_content_type = content_type
    job.result_checksum = checksum
    job.result_row_count = row_count
    job.result_truncated = truncated
    job.result_summary = f"Exported {row_count} task rows."
    job.completed_at = now
    job.version += 1
    session.commit()


def settle_failure(
    session: Session,
    job_id: UUID,
    attempt_id: UUID,
    *,
    code: str,
    retryable: bool,
    retry_exhausted: bool = False,
) -> None:
    job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    attempt = session.scalar(
        select(JobAttempt)
        .where(JobAttempt.id == attempt_id, JobAttempt.job_id == job_id)
        .with_for_update()
    )
    if (
        not job
        or not attempt
        or job.status != JobStatus.RUNNING
        or attempt.status != AttemptStatus.RUNNING
    ):
        raise JobError("STALE_SETTLEMENT", "The execution attempt is no longer active.", 409)
    attempt.finished_at = datetime.now(UTC)
    attempt.failure_code = code
    attempt.retryable = retryable
    if retryable and not retry_exhausted:
        attempt.status = AttemptStatus.RETRY_SCHEDULED
        attempt.safe_summary = "Execution will be retried."
        job.status = JobStatus.QUEUED
    else:
        attempt.status = AttemptStatus.FAILED
        attempt.safe_summary = "Execution failed."
        job.status = JobStatus.FAILED
        job.failure_classification = code
        job.completed_at = datetime.now(UTC)
    job.version += 1
    session.commit()
