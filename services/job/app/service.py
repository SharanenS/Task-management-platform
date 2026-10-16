import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Job, JobAttempt, JobStatus, JobType
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
