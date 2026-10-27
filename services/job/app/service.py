import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    AttemptStatus,
    Job,
    JobAttempt,
    JobStatus,
    JobType,
    OutboxEvent,
    PublicationStatus,
)
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
EXECUTION_LEASE_SECONDS = 30
MAX_AUTOMATIC_ATTEMPTS = 3
MAX_MANUAL_RETRIES = 1


@dataclass(frozen=True)
class Actor:
    employee_id: UUID
    application_role: str


@dataclass(frozen=True)
class Page:
    items: list[Job]
    next_cursor: str | None
    has_next_page: bool


@dataclass(frozen=True)
class PublicationPage:
    items: list[OutboxEvent]
    next_cursor: str | None
    has_next_page: bool


class JobError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


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


def list_publications(
    session: Session,
    actor: Actor,
    *,
    first: int = 20,
    after: str | None = None,
    status: PublicationStatus | None = None,
) -> PublicationPage:
    if actor.application_role != "ADMIN":
        raise JobError("FORBIDDEN", "Administrator access is required.", 403)
    if first < 1 or first > 50:
        raise JobError("INVALID_PAGE_SIZE", "The page size must be between 1 and 50.")
    statement = select(OutboxEvent)
    if status:
        statement = statement.where(OutboxEvent.status == status)
    if after:
        created_at, event_id = _decode_cursor(after)
        statement = statement.where(
            or_(
                OutboxEvent.created_at < created_at,
                and_(OutboxEvent.created_at == created_at, OutboxEvent.id < event_id),
            )
        )
    items = list(
        session.scalars(
            statement.order_by(OutboxEvent.created_at.desc(), OutboxEvent.id.desc()).limit(
                first + 1
            )
        )
    )
    has_next_page = len(items) > first
    items = items[:first]
    cursor = None
    if has_next_page:
        last = items[-1]
        raw = json.dumps([last.created_at.isoformat(), str(last.id)], separators=(",", ":"))
        cursor = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    return PublicationPage(items, cursor, has_next_page)


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
    _obsolete_publisher: object | None = None,
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
    job.execution_generation = 1
    job.version += 1
    session.add(
        OutboxEvent(
            job_id=job.id,
            event_type="EXECUTE_JOB",
            schema_version=1,
            execution_generation=1,
            status=PublicationStatus.PENDING,
        )
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise JobError(
            "JOB_NOT_DISPATCHABLE", "The job cannot be dispatched in its current state.", 409
        ) from None
    session.refresh(job)
    return job


def claim_publications(
    session: Session, *, batch_size: int = 20, lease_seconds: int = 30, now: datetime | None = None
) -> list[OutboxEvent]:
    current = now or datetime.now(UTC)
    eligible = or_(
        and_(
            OutboxEvent.status.in_([PublicationStatus.PENDING, PublicationStatus.FAILED]),
            OutboxEvent.available_at <= current,
        ),
        and_(
            OutboxEvent.status == PublicationStatus.IN_FLIGHT,
            OutboxEvent.lease_expires_at <= current,
        ),
    )
    events = list(
        session.scalars(
            select(OutboxEvent)
            .where(eligible)
            .order_by(OutboxEvent.created_at, OutboxEvent.id)
            .limit(min(max(batch_size, 1), 100))
            .with_for_update(skip_locked=True)
        )
    )
    for event in events:
        event.status = PublicationStatus.IN_FLIGHT
        event.lease_token = secrets.token_hex(24)
        event.lease_expires_at = current + timedelta(seconds=lease_seconds)
        event.attempt_count += 1
    session.commit()
    return events


def settle_publication_success(session: Session, event_id: UUID, lease_token: str) -> bool:
    event = session.scalar(select(OutboxEvent).where(OutboxEvent.id == event_id).with_for_update())
    if (
        not event
        or event.status != PublicationStatus.IN_FLIGHT
        or not secrets.compare_digest(event.lease_token or "", lease_token)
    ):
        session.rollback()
        return False
    event.status = PublicationStatus.PUBLISHED
    event.published_at = datetime.now(UTC)
    event.lease_token = None
    event.lease_expires_at = None
    event.last_failure_classification = None
    session.commit()
    return True


def settle_publication_failure(
    session: Session, event_id: UUID, lease_token: str, classification: str
) -> bool:
    allowed = {"CONNECTION_FAILED", "CONFIRMATION_REJECTED", "CONFIRMATION_AMBIGUOUS"}
    fixed = classification if classification in allowed else "PUBLICATION_FAILED"
    event = session.scalar(select(OutboxEvent).where(OutboxEvent.id == event_id).with_for_update())
    if (
        not event
        or event.status != PublicationStatus.IN_FLIGHT
        or not secrets.compare_digest(event.lease_token or "", lease_token)
    ):
        session.rollback()
        return False
    event.status = PublicationStatus.FAILED
    event.available_at = datetime.now(UTC) + timedelta(
        seconds=min(2 ** min(event.attempt_count, 6), 60)
    )
    event.last_failure_classification = fixed
    event.lease_token = None
    event.lease_expires_at = None
    session.commit()
    return True


def claim_job(
    session: Session,
    job_id: UUID,
    *,
    now: datetime | None = None,
    lease_seconds: int = EXECUTION_LEASE_SECONDS,
) -> JobAttempt | None:
    current = now or datetime.now(UTC)
    job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if job is None or job.status != JobStatus.QUEUED:
        return None
    attempt_number = (
        int(
            session.scalar(
                select(func.coalesce(func.max(JobAttempt.attempt_number), 0)).where(
                    JobAttempt.job_id == job.id
                )
            )
            or 0
        )
        + 1
    )
    fence = (
        int(
            session.scalar(
                select(func.coalesce(func.max(JobAttempt.execution_fence), 0)).where(
                    JobAttempt.job_id == job.id
                )
            )
            or 0
        )
        + 1
    )
    attempt = JobAttempt(
        job_id=job.id,
        attempt_number=attempt_number,
        status=AttemptStatus.RUNNING,
        retryable=False,
        execution_generation=job.execution_generation,
        execution_fence=fence,
        execution_lease_token=secrets.token_hex(24),
        lease_acquired_at=current,
        lease_expires_at=current + timedelta(seconds=lease_seconds),
        last_heartbeat_at=current,
    )
    job.status = JobStatus.RUNNING
    job.version += 1
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return attempt


def heartbeat_execution(
    session: Session,
    attempt_id: UUID,
    lease_token: str,
    execution_fence: int,
    *,
    now: datetime | None = None,
    lease_seconds: int = EXECUTION_LEASE_SECONDS,
) -> bool:
    current = now or datetime.now(UTC)
    attempt = session.scalar(
        select(JobAttempt)
        .where(
            JobAttempt.id == attempt_id,
            JobAttempt.status == AttemptStatus.RUNNING,
            JobAttempt.execution_lease_token == lease_token,
            JobAttempt.execution_fence == execution_fence,
            JobAttempt.lease_expires_at > current,
        )
        .with_for_update()
    )
    if attempt is None:
        session.rollback()
        return False
    attempt.last_heartbeat_at = current
    attempt.lease_expires_at = current + timedelta(seconds=lease_seconds)
    session.commit()
    return True


def _owns_execution(
    attempt: JobAttempt, lease_token: str | None, execution_fence: int | None
) -> bool:
    return bool(
        lease_token
        and execution_fence is not None
        and attempt.execution_lease_token
        and secrets.compare_digest(attempt.execution_lease_token, lease_token)
        and attempt.execution_fence == execution_fence
    )


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
    lease_token: str | None = None,
    execution_fence: int | None = None,
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
        or not _owns_execution(attempt, lease_token, execution_fence)
    ):
        raise JobError("STALE_SETTLEMENT", "The execution attempt is no longer active.", 409)
    now = datetime.now(UTC)
    attempt.status = AttemptStatus.SUCCEEDED
    attempt.finished_at = now
    attempt.execution_lease_token = None
    attempt.lease_expires_at = None
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
    lease_token: str | None = None,
    execution_fence: int | None = None,
    now: datetime | None = None,
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
        or not _owns_execution(attempt, lease_token, execution_fence)
    ):
        raise JobError("STALE_SETTLEMENT", "The execution attempt is no longer active.", 409)
    current = now or datetime.now(UTC)
    attempt.finished_at = current
    attempt.execution_lease_token = None
    attempt.lease_expires_at = None
    attempt.failure_code = code
    attempt.retryable = retryable
    exhausted = retry_exhausted or attempt.attempt_number >= MAX_AUTOMATIC_ATTEMPTS
    if retryable and not exhausted:
        attempt.status = AttemptStatus.RETRY_SCHEDULED
        attempt.safe_summary = "Execution will be retried."
        attempt.retry_scheduled_at = current
        job.status = JobStatus.QUEUED
        job.execution_generation += 1
        delay = min(2**attempt.attempt_number, 30)
        session.add(
            OutboxEvent(
                job_id=job.id,
                execution_generation=job.execution_generation,
                status=PublicationStatus.PENDING,
                available_at=current + timedelta(seconds=delay),
            )
        )
    else:
        attempt.status = AttemptStatus.FAILED
        attempt.safe_summary = "Execution failed."
        job.status = JobStatus.FAILED
        job.failure_classification = code
        job.completed_at = current
        job.retry_exhausted = bool(retryable)
    job.version += 1
    session.commit()


def recover_expired_executions(
    session: Session,
    *,
    batch_size: int = 20,
    now: datetime | None = None,
) -> list[UUID]:
    current = now or datetime.now(UTC)
    attempts = list(
        session.scalars(
            select(JobAttempt)
            .where(
                JobAttempt.status == AttemptStatus.RUNNING,
                JobAttempt.lease_expires_at <= current,
            )
            .order_by(JobAttempt.lease_expires_at, JobAttempt.id)
            .limit(min(max(batch_size, 1), 100))
            .with_for_update(skip_locked=True)
        )
    )
    recovered: list[UUID] = []
    for attempt in attempts:
        job = session.scalar(select(Job).where(Job.id == attempt.job_id).with_for_update())
        if not job or job.status != JobStatus.RUNNING or attempt.status != AttemptStatus.RUNNING:
            continue
        attempt.status = AttemptStatus.ABANDONED
        attempt.abandoned_at = current
        attempt.recovered_at = current
        attempt.finished_at = current
        attempt.failure_code = "EXECUTION_LEASE_EXPIRED"
        attempt.safe_summary = "Execution ownership expired and was recovered."
        attempt.retryable = True
        attempt.execution_lease_token = None
        attempt.lease_expires_at = None
        if attempt.attempt_number >= MAX_AUTOMATIC_ATTEMPTS:
            job.status = JobStatus.FAILED
            job.retry_exhausted = True
            job.failure_classification = "RETRY_EXHAUSTED"
            job.completed_at = current
        else:
            attempt.retry_scheduled_at = current
            job.status = JobStatus.QUEUED
            job.execution_generation += 1
            session.add(
                OutboxEvent(
                    job_id=job.id,
                    execution_generation=job.execution_generation,
                    status=PublicationStatus.PENDING,
                    available_at=current,
                )
            )
        job.version += 1
        recovered.append(job.id)
    session.commit()
    return recovered


def admin_retry_job(
    session: Session,
    actor: Actor,
    job_id: UUID,
    expected_version: int,
) -> Job:
    if actor.application_role != "ADMIN":
        raise JobError("FORBIDDEN", "Administrator access is required.", 403)
    job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if not job:
        raise JobError("JOB_NOT_FOUND", "The job was not found.", 404)
    if job.version != expected_version:
        raise JobError("VERSION_CONFLICT", "The job changed before it could be retried.", 409)
    if job.status != JobStatus.FAILED or job.manual_retry_count >= MAX_MANUAL_RETRIES:
        raise JobError(
            "JOB_NOT_RETRYABLE", "The job is not eligible for administrative retry.", 409
        )
    if session.scalar(
        select(JobAttempt).where(
            JobAttempt.job_id == job.id, JobAttempt.status == AttemptStatus.RUNNING
        )
    ):
        raise JobError("JOB_NOT_RETRYABLE", "The job has an active execution.", 409)
    job.status = JobStatus.QUEUED
    job.completed_at = None
    job.failure_classification = None
    job.retry_exhausted = False
    job.manual_retry_count += 1
    job.execution_generation += 1
    job.version += 1
    session.add(
        OutboxEvent(
            job_id=job.id,
            execution_generation=job.execution_generation,
            status=PublicationStatus.PENDING,
        )
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise JobError("JOB_RETRY_CONFLICT", "The retry request conflicted.", 409) from None
    session.refresh(job)
    return job
