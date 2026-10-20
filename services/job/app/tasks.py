from uuid import UUID

from celery import Task

from app.celery_app import celery_app
from app.db import SessionLocal
from app.execution import ExecutionFailure, execute_project_task_export
from app.models import Job, JobType
from app.publisher import TASK_NAME
from app.service import claim_job, settle_failure, settle_success

MAX_RETRIES = 2


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True, name=TASK_NAME, autoretry_for=(), max_retries=MAX_RETRIES
)
def execute_job(self: Task, job_id: str) -> None:
    identifier = UUID(job_id)
    with SessionLocal() as session:
        attempt = claim_job(session, identifier)
        if attempt is None:
            return
        job = session.get(Job, identifier)
        if job is None:
            return
        try:
            if job.job_type != JobType.PROJECT_TASK_EXPORT:
                raise ExecutionFailure("UNSUPPORTED_JOB_TYPE", retryable=False)
            result = execute_project_task_export(job.submitter_employee_id, job.payload)
            settle_success(
                session,
                job.id,
                attempt.id,
                content=result.content,
                content_type=result.content_type,
                checksum=result.checksum,
                row_count=result.row_count,
                truncated=result.truncated,
            )
        except ExecutionFailure as error:
            exhausted = not error.retryable or self.request.retries >= MAX_RETRIES
            settle_failure(
                session,
                job.id,
                attempt.id,
                code=error.code,
                retryable=error.retryable,
                retry_exhausted=exhausted,
            )
            if error.retryable and not exhausted:
                raise self.retry(countdown=min(2 ** (self.request.retries + 1), 8)) from None
