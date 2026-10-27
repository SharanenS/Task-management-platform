from threading import Event, Thread
from uuid import UUID

from celery import Task

from app.celery_app import celery_app
from app.db import SessionLocal
from app.execution import ExecutionFailure, execute_project_task_export
from app.models import Job, JobType
from app.publisher import TASK_NAME
from app.service import claim_job, heartbeat_execution, settle_failure, settle_success


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True, name=TASK_NAME, autoretry_for=(), max_retries=0
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
        lease_token = attempt.execution_lease_token or ""
        fence = attempt.execution_fence
        stopped = Event()
        authority_lost = Event()

        def heartbeat() -> None:
            while not stopped.wait(10):
                with SessionLocal() as heartbeat_session:
                    if not heartbeat_execution(heartbeat_session, attempt.id, lease_token, fence):
                        authority_lost.set()
                        return

        heartbeat_thread = Thread(target=heartbeat, daemon=True)
        heartbeat_thread.start()
        try:
            if job.job_type != JobType.PROJECT_TASK_EXPORT:
                raise ExecutionFailure("UNSUPPORTED_JOB_TYPE", retryable=False)
            result = execute_project_task_export(job.submitter_employee_id, job.payload)
            stopped.set()
            heartbeat_thread.join(timeout=2)
            if authority_lost.is_set():
                return
            settle_success(
                session,
                job.id,
                attempt.id,
                content=result.content,
                content_type=result.content_type,
                checksum=result.checksum,
                row_count=result.row_count,
                truncated=result.truncated,
                lease_token=lease_token,
                execution_fence=fence,
            )
        except ExecutionFailure as error:
            stopped.set()
            heartbeat_thread.join(timeout=2)
            if authority_lost.is_set():
                return
            settle_failure(
                session,
                job.id,
                attempt.id,
                code=error.code,
                retryable=error.retryable,
                lease_token=lease_token,
                execution_fence=fence,
            )
        finally:
            stopped.set()
