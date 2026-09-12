"""Asynchronous job execution engine interacting with PostgreSQL."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.constants import JobStatus
from app.core.logging import get_logger
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


async def _execute_handler_and_settle(
    session: AsyncSession,
    job_service: JobService,
    job: Job,
    claim_owner: str,
) -> None:
    """Execute handler and settle result via fenced repository methods."""
    handler = get_handler(job.job_type)
    if not handler:
        err_msg = f"Unknown or unsupported job type: '{job.job_type}'"
        logger.error("unknown_job_type", job_id=str(job.id), job_type=job.job_type)
        failed = await job_service.fail_job(job.id, claim_owner=claim_owner, error_message=err_msg)
        await session.commit()
        if failed is None:
            logger.warning("failed_to_mark_unknown_job_lost_ownership", job_id=str(job.id), claim_owner=claim_owner)
        return

    try:
        handler(job.payload)
        completed = await job_service.complete_job(job.id, claim_owner=claim_owner)
        await session.commit()
        if completed is None:
            logger.warning("job_completion_lost_ownership", job_id=str(job.id), claim_owner=claim_owner)
            return
        logger.info("job_completed_successfully", job_id=str(job.id), job_type=job.job_type, claim_owner=claim_owner)
    except Exception as e:
        err_msg = str(e) or f"Execution failed with {type(e).__name__}"
        logger.error("job_execution_failed", job_id=str(job.id), error=err_msg, claim_owner=claim_owner)
        try:
            failed = await job_service.fail_job(job.id, claim_owner=claim_owner, error_message=err_msg)
            await session.commit()
            if failed is None:
                logger.warning("job_failure_lost_ownership", job_id=str(job.id), claim_owner=claim_owner)
        except Exception as record_err:
            logger.error("failed_to_record_job_failure", job_id=str(job.id), error=str(record_err))
            await session.rollback()


async def execute_job_by_id(job_id: uuid.UUID, claim_owner: str | None = None) -> None:
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
            # ── Recovered Delivery Path ─────────────────────────────────────
            job = await job_repo.get_by_id(job_id)
            if not job:
                logger.warning("recovered_job_not_found", job_id=str(job_id))
                return
            if job.status != JobStatus.PROCESSING:
                logger.info("recovered_job_not_processing_skipping", job_id=str(job_id), status=job.status)
                return
            if job.execution_claim_owner != claim_owner:
                logger.warning(
                    "recovered_job_claim_owner_mismatch_skipping",
                    job_id=str(job_id),
                    expected_owner=claim_owner,
                    actual_owner=job.execution_claim_owner,
                )
                return
            now_utc = datetime.now(timezone.utc)
            if job.execution_lease_until is not None and job.execution_lease_until < now_utc:
                logger.warning("recovered_job_lease_expired_skipping", job_id=str(job_id), claim_owner=claim_owner)
                return

            await _execute_handler_and_settle(session, job_service, job, claim_owner)
        else:
            # ── Normal Delivery Path ────────────────────────────────────────
            owner = f"worker-{uuid.uuid4().hex[:8]}"
            job = await job_service.claim_job(
                job_id,
                claim_owner=owner,
                lease_seconds=settings.JOB_EXECUTION_LEASE_SECONDS,
            )
            if not job:
                existing_job = await job_repo.get_by_id(job_id)
                if not existing_job:
                    logger.warning("job_not_found_for_execution", job_id=str(job_id))
                elif existing_job.status in {JobStatus.COMPLETED, JobStatus.FAILED}:
                    logger.info(
                        "job_already_terminal_skipping",
                        job_id=str(job_id),
                        status=existing_job.status,
                    )
                elif existing_job.status == JobStatus.PROCESSING:
                    logger.info("job_already_claimed_skipping", job_id=str(job_id))
                return

            # Commit ownership immediately so other workers see PROCESSING with active lease
            await session.commit()

            await _execute_handler_and_settle(session, job_service, job, owner)
