"""Asynchronous job execution engine interacting with PostgreSQL."""

import re
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.constants import JobStatus
from app.core.logging import get_logger, sanitize_error
from app.core.metrics import metrics
from app.models.job import Job
from app.repositories.job import JobRepository
from app.repositories.project import ProjectRepository
from app.services.job import JobService
from app.tasks.handlers import get_handler

logger = get_logger(__name__)

# Dedicated engine for worker tasks with NullPool to prevent event loop connection pooling conflicts across Celery tasks
worker_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    poolclass=NullPool,
)

worker_session_factory = async_sessionmaker(
    worker_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# sanitize_error imported from app.core.logging


async def _execute_handler_and_settle(
    session: AsyncSession,
    job_service: JobService,
    job: Job,
    claim_owner: str,
    celery_task_id: str | None = None,
) -> None:
    """Execute handler and settle result via fenced repository methods."""
    handler = get_handler(job.job_type)
    if not handler:
        err_msg = f"Unknown or unsupported job type: '{job.job_type}'"
        logger.error(
            "unknown_job_type_execution_failed",
            job_id=str(job.id),
            job_type=job.job_type,
            claim_owner=claim_owner,
            error=err_msg,
            celery_task_id=celery_task_id,
        )
        failed = await job_service.fail_job(job.id, claim_owner=claim_owner, error_message=err_msg)
        await session.commit()
        if failed is None:
            logger.warning(
                "stale_worker_failure_rejected",
                job_id=str(job.id),
                job_type=job.job_type,
                claim_owner=claim_owner,
                reason="ownership_lost_or_lease_expired",
                celery_task_id=celery_task_id,
            )
        return

    logger.info(
        "job_execution_started",
        job_id=str(job.id),
        job_type=job.job_type,
        claim_owner=claim_owner,
        processing_started_at=job.processing_started_at.isoformat() if job.processing_started_at else None,
        execution_lease_until=job.execution_lease_until.isoformat() if job.execution_lease_until else None,
        celery_task_id=celery_task_id,
    )

    start_time = time.perf_counter()
    try:
        handler(job.payload)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        completed = await job_service.complete_job(job.id, claim_owner=claim_owner)
        await session.commit()
        if completed is None:
            logger.warning(
                "stale_worker_completion_rejected",
                job_id=str(job.id),
                job_type=job.job_type,
                claim_owner=claim_owner,
                reason="ownership_lost_or_lease_expired",
                celery_task_id=celery_task_id,
            )
            return
        metrics.record_job_execution(job_type=job.job_type, outcome="success", duration_seconds=duration_ms / 1000.0)
        logger.info(
            "job_execution_completed",
            job_id=str(job.id),
            job_type=job.job_type,
            claim_owner=claim_owner,
            duration_ms=duration_ms,
            celery_task_id=celery_task_id,
        )
    except Exception as e:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        err_msg = str(e) or f"Execution failed with {type(e).__name__}"
        safe_err = sanitize_error(err_msg)
        metrics.record_job_execution(job_type=job.job_type, outcome="failure", duration_seconds=duration_ms / 1000.0, error_type=type(e).__name__)
        logger.error(
            "job_execution_failed",
            job_id=str(job.id),
            job_type=job.job_type,
            claim_owner=claim_owner,
            error=safe_err,
            error_type=type(e).__name__,
            duration_ms=duration_ms,
            celery_task_id=celery_task_id,
        )
        try:
            failed = await job_service.fail_job(job.id, claim_owner=claim_owner, error_message=safe_err)
            await session.commit()
            if failed is None:
                logger.warning(
                    "stale_worker_failure_rejected",
                    job_id=str(job.id),
                    job_type=job.job_type,
                    claim_owner=claim_owner,
                    reason="ownership_lost_or_lease_expired",
                    celery_task_id=celery_task_id,
                )
        except Exception as record_err:
            logger.error(
                "failed_to_record_job_failure",
                job_id=str(job.id),
                error=sanitize_error(str(record_err)),
                celery_task_id=celery_task_id,
            )
            await session.rollback()


async def execute_job_by_id(
    job_id: uuid.UUID,
    claim_owner: str | None = None,
    celery_task_id: str | None = None,
) -> None:
    """
    Authoritative worker execution flow for a background job.

    Supports two delivery modes:
    1. Normal delivery (claim_owner is None):
       - Generates unique worker claim owner.
       - Atomically claims QUEUED -> PROCESSING with lease.
       - Commits claim transaction immediately.
       - Executes handler and performs fenced completion/failure.
    2. Recovered delivery (claim_owner is provided):
       - Job was already claimed into PROCESSING by recovery process.
       - Verifies status == PROCESSING, owner matches claim_owner, and lease is unexpired.
       - Executes handler and performs fenced completion/failure.
    """
    async with worker_session_factory() as session:
        job_repo = JobRepository(session)
        project_repo = ProjectRepository(session)
        job_service = JobService(repository=job_repo, project_repository=project_repo)

        if claim_owner is not None:
            # ── Recovered Delivery Path ──────────────────────────────────────────
            job = await job_repo.get_by_id(job_id)
            if not job:
                logger.warning("recovered_job_not_found", job_id=str(job_id), celery_task_id=celery_task_id)
                return
            if job.status != JobStatus.PROCESSING:
                logger.info(
                    "recovered_job_not_processing_skipping",
                    job_id=str(job_id),
                    status=str(job.status),
                    celery_task_id=celery_task_id,
                )
                return
            if job.execution_claim_owner != claim_owner:
                logger.warning(
                    "recovered_job_claim_owner_mismatch_skipping",
                    job_id=str(job_id),
                    expected_owner=claim_owner,
                    actual_owner=job.execution_claim_owner,
                    celery_task_id=celery_task_id,
                )
                return
            now_utc = datetime.now(timezone.utc)
            if job.execution_lease_until is not None and job.execution_lease_until < now_utc:
                logger.warning(
                    "recovered_job_lease_expired_skipping",
                    job_id=str(job_id),
                    claim_owner=claim_owner,
                    celery_task_id=celery_task_id,
                )
                return

            logger.info(
                "recovered_job_claim_verified",
                job_id=str(job.id),
                job_type=job.job_type,
                claim_owner=claim_owner,
                celery_task_id=celery_task_id,
            )
            await _execute_handler_and_settle(session, job_service, job, claim_owner, celery_task_id=celery_task_id)
        else:
            # ── Normal Delivery Path ─────────────────────────────────────────────
            owner = f"worker-{uuid.uuid4().hex[:8]}"
            job = await job_service.claim_job(
                job_id,
                claim_owner=owner,
                lease_seconds=settings.JOB_EXECUTION_LEASE_SECONDS,
            )
            if not job:
                existing_job = await job_repo.get_by_id(job_id)
                if not existing_job:
                    logger.warning("job_not_found_for_execution", job_id=str(job_id), celery_task_id=celery_task_id)
                elif existing_job.status in {JobStatus.COMPLETED, JobStatus.FAILED}:
                    logger.info(
                        "job_already_terminal_skipping",
                        job_id=str(job_id),
                        status=str(existing_job.status),
                        celery_task_id=celery_task_id,
                    )
                elif existing_job.status == JobStatus.PROCESSING:
                    logger.info(
                        "duplicate_delivery_skipped",
                        job_id=str(job_id),
                        current_status=str(existing_job.status),
                        celery_task_id=celery_task_id,
                    )
                return

            # Commit ownership immediately so other workers see PROCESSING with active lease
            await session.commit()

            logger.info(
                "job_claimed_by_worker",
                job_id=str(job.id),
                job_type=job.job_type,
                claim_owner=owner,
                lease_seconds=settings.JOB_EXECUTION_LEASE_SECONDS,
                celery_task_id=celery_task_id,
            )
            await _execute_handler_and_settle(session, job_service, job, owner, celery_task_id=celery_task_id)
