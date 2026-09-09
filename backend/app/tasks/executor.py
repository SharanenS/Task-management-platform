"""Asynchronous job execution engine interacting with PostgreSQL."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.constants import JobStatus
from app.core.logging import get_logger
from app.repositories.job import JobRepository
from app.repositories.project import ProjectRepository
from app.schemas.job import JobStatusUpdate
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


async def execute_job_by_id(job_id: uuid.UUID) -> None:
    """
    Authoritative worker execution flow for a background job:
    1. Atomically claim the Job from QUEUED to PROCESSING.
    2. If not claimable (missing, already PROCESSING, or terminal COMPLETED/FAILED), skip.
    3. Resolve handler from registry by job_type.
    4. Execute handler.
    5. Transition to COMPLETED on success, or FAILED on exception with error_message.
    """
    async with worker_session_factory() as session:
        job_repo = JobRepository(session)
        project_repo = ProjectRepository(session)
        job_service = JobService(repository=job_repo, project_repository=project_repo)

        # 1. Attempt atomic claim of QUEUED -> PROCESSING
        job = await job_service.claim_job(job_id)
        if not job:
            # Check current state to log appropriate skip reason
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

        # Commit the claimed state immediately so other workers see PROCESSING
        await session.commit()

        # 2. Resolve handler from registry
        handler = get_handler(job.job_type)
        if not handler:
            err_msg = f"Unknown or unsupported job type: '{job.job_type}'"
            logger.error("unknown_job_type", job_id=str(job_id), job_type=job.job_type)
            try:
                await job_service.update_status(
                    job_id,
                    JobStatusUpdate(status=JobStatus.FAILED, error_message=err_msg),
                )
                await session.commit()
            except Exception as update_err:
                logger.error("failed_to_mark_job_failed_for_unknown_type", job_id=str(job_id), error=str(update_err))
                await session.rollback()
            return

        # 3. Execute handler
        try:
            handler(job.payload)
            # 4. Success: Transition to COMPLETED
            await job_service.update_status(
                job_id,
                JobStatusUpdate(status=JobStatus.COMPLETED),
            )
            await session.commit()
            logger.info("job_completed_successfully", job_id=str(job_id), job_type=job.job_type)
        except Exception as e:
            # 5. Failure: Transition to FAILED and persist error message
            err_msg = str(e) or f"Execution failed with {type(e).__name__}"
            try:
                logger.error("job_execution_failed", job_id=str(job_id), error=err_msg)
            except Exception:
                pass

            try:
                await job_service.update_status(
                    job_id,
                    JobStatusUpdate(status=JobStatus.FAILED, error_message=err_msg),
                )
                await session.commit()
            except Exception as update_err:
                try:
                    logger.error("failed_to_mark_job_failed", job_id=str(job_id), error=str(update_err))
                except Exception:
                    pass
                await session.rollback()
