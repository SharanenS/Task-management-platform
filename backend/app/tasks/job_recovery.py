"""Background daemon service for recovering expired PROCESSING jobs."""

import asyncio
import signal
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.logging import get_logger
from app.models.job import Job
from app.repositories.job import JobRepository
from app.tasks.jobs import process_job_task

logger = get_logger(__name__)

# Dedicated engine for recovery daemon with NullPool to avoid connection pooling issues
recovery_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    poolclass=NullPool,
)

recovery_session_factory = async_sessionmaker(
    recovery_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def reclaim_batch(
    batch_size: int,
    lease_seconds: int,
    recovery_id: str,
) -> Sequence[Job]:
    """Atomically acquire new execution leases on expired PROCESSING jobs in a short DB transaction."""
    async with recovery_session_factory() as session:
        repo = JobRepository(session)
        jobs = await repo.reclaim_expired_jobs(
            limit=batch_size,
            claim_owner=recovery_id,
            lease_seconds=lease_seconds,
        )
        await session.commit()
        return jobs


async def recover_and_dispatch_jobs(
    batch_size: int | None = None,
    lease_seconds: int | None = None,
    recovery_id: str | None = None,
) -> int:
    """
    Recover expired PROCESSING jobs:
    1. Atomically reclaim expired jobs in PostgreSQL and commit the new lease ownership.
    2. After DB commit, dispatch Celery tasks passing the recovery claim owner.
    Returns the count of successfully reclaimed and dispatched jobs.
    """
    b_size = batch_size if batch_size is not None else settings.JOB_RECOVERY_BATCH_SIZE
    l_secs = lease_seconds if lease_seconds is not None else settings.JOB_EXECUTION_LEASE_SECONDS
    rec_id = recovery_id or f"recovery-{uuid.uuid4().hex[:8]}"

    reclaimed_jobs = await reclaim_batch(
        batch_size=b_size,
        lease_seconds=l_secs,
        recovery_id=rec_id,
    )
    if not reclaimed_jobs:
        return 0

    logger.info("expired_jobs_reclaimed", count=len(reclaimed_jobs), recovery_id=rec_id)

    dispatched_count = 0
    for job in reclaimed_jobs:
        try:
            process_job_task.delay(str(job.id), claim_owner=rec_id)
            dispatched_count += 1
            logger.info("reclaimed_job_dispatched", job_id=str(job.id), recovery_id=rec_id)
        except Exception as e:
            logger.error(
                "failed_to_dispatch_reclaimed_job",
                job_id=str(job.id),
                recovery_id=rec_id,
                error=str(e),
            )

    return dispatched_count


async def run_recovery_loop(
    poll_interval: float | None = None,
    batch_size: int | None = None,
    lease_seconds: int | None = None,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Run continuous recovery polling loop with configurable intervals and graceful shutdown."""
    interval = poll_interval if poll_interval is not None else settings.JOB_RECOVERY_POLL_INTERVAL_SECONDS
    b_size = batch_size if batch_size is not None else settings.JOB_RECOVERY_BATCH_SIZE
    l_secs = lease_seconds if lease_seconds is not None else settings.JOB_EXECUTION_LEASE_SECONDS
    stop = stop_event or asyncio.Event()
    rec_id = f"recovery-{uuid.uuid4().hex[:8]}"

    logger.info(
        "job_recovery_service_started",
        recovery_id=rec_id,
        poll_interval=interval,
        batch_size=b_size,
        lease_seconds=l_secs,
    )

    while not stop.is_set():
        try:
            recovered = await recover_and_dispatch_jobs(
                batch_size=b_size,
                lease_seconds=l_secs,
                recovery_id=rec_id,
            )
            if recovered == 0:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=interval)
                except asyncio.TimeoutError:
                    pass
        except Exception as e:
            logger.error("job_recovery_loop_error", error=str(e))
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    logger.info("job_recovery_service_stopped", recovery_id=rec_id)


def main() -> None:
    """Main entrypoint for running job recovery as a standalone worker process."""
    stop_event = asyncio.Event()

    def _handle_signal(*_: Any) -> None:
        logger.info("job_recovery_shutdown_signal_received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle_signal)
        except Exception:
            pass

    try:
        asyncio.run(run_recovery_loop(stop_event=stop_event))
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
