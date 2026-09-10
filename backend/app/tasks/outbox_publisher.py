"""Transactional Outbox Publisher.

Periodically polls PostgreSQL for PENDING outbox events using FOR UPDATE SKIP LOCKED,
dispatches them to RabbitMQ via Celery, and marks them PUBLISHED.
Guarantees at-least-once publication without blocking concurrent publisher instances.
"""

import asyncio
import signal
import sys
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.constants import OutboxEventType
from app.core.logging import get_logger
from app.models.outbox import OutboxEvent
from app.repositories.outbox import OutboxRepository

logger = get_logger(__name__)

# Dedicated engine with NullPool to prevent connection pool / event loop conflicts across async tasks
publisher_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    poolclass=NullPool,
)

publisher_session_factory = async_sessionmaker(
    publisher_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def _dispatch_event(event: OutboxEvent) -> None:
    """Dispatch the outbox event payload to the target message broker/queue."""
    if event.event_type == OutboxEventType.JOB_CREATED:
        job_id = event.payload.get("job_id")
        if not job_id:
            raise ValueError(f"Outbox event {event.id} missing required 'job_id' in payload")
        from app.tasks.jobs import process_job_task

        process_job_task.delay(str(job_id))
    else:
        raise ValueError(f"Unsupported outbox event_type: {event.event_type}")


async def publish_single_event(session: AsyncSession, event: OutboxEvent) -> bool:
    """
    Publish a single outbox event to RabbitMQ and commit its state in PostgreSQL.
    Returns True if published successfully, False otherwise.
    """
    outbox_repo = OutboxRepository(session)
    event_id = event.id
    aggregate_id = str(event.aggregate_id)
    event_type = str(event.event_type)
    attempt_count = event.attempt_count

    try:
        _dispatch_event(event)
        await outbox_repo.mark_published(event_id)
        await session.commit()
        logger.info(
            "outbox_event_published",
            outbox_id=str(event_id),
            event_type=event_type,
            aggregate_id=aggregate_id,
        )
        return True
    except Exception as e:
        err_msg = str(e) or type(e).__name__
        logger.error(
            "outbox_event_publish_failed",
            outbox_id=str(event_id),
            attempt=attempt_count + 1,
            error=err_msg,
        )
        try:
            await session.rollback()
            await outbox_repo.record_failure(event_id, err_msg)
            await session.commit()
        except Exception as record_err:
            logger.error(
                "failed_to_record_outbox_failure",
                outbox_id=str(event_id),
                error=str(record_err),
            )
            await session.rollback()
        return False


async def publish_pending_events(batch_size: int = 50) -> int:
    """
    Poll and publish a batch of pending outbox events using FOR UPDATE SKIP LOCKED.
    Safe for multiple concurrent publisher processes.
    Returns the count of successfully published events.
    """
    published_count = 0
    async with publisher_session_factory() as session:
        outbox_repo = OutboxRepository(session)
        events = await outbox_repo.get_pending_events(limit=batch_size)
        if not events:
            return 0

        logger.info("outbox_pending_events_claimed", count=len(events))
        for event in events:
            success = await publish_single_event(session, event)
            if success:
                published_count += 1

    return published_count


async def run_publisher_loop(
    poll_interval: float = 1.0,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Run continuous publisher polling loop."""
    logger.info("outbox_publisher_service_started", poll_interval=poll_interval)
    stop = stop_event or asyncio.Event()

    while not stop.is_set():
        try:
            published = await publish_pending_events()
            if published == 0:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=poll_interval)
                except asyncio.TimeoutError:
                    pass
        except Exception as e:
            logger.error("outbox_publisher_loop_error", error=str(e))
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_interval)
            except asyncio.TimeoutError:
                pass

    logger.info("outbox_publisher_service_stopped")


def main() -> None:
    """Main entrypoint for running outbox publisher as a standalone worker process."""
    stop_event = asyncio.Event()

    def _handle_signal(*_: Any) -> None:
        logger.info("shutdown_signal_received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle_signal)
        except Exception:
            pass

    try:
        asyncio.run(run_publisher_loop(poll_interval=1.0, stop_event=stop_event))
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
