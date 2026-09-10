"""Transactional Outbox Publisher with Short-Lived Leases.

Periodically claims eligible outbox events in a short database transaction using
FOR UPDATE SKIP LOCKED and a lease duration.
Publishes events to RabbitMQ via Celery outside the database claim transaction,
then marks events PUBLISHED or records failure in separate short transactions with lease ownership verification.
Guarantees at-least-once publication, multi-instance scalability, and automatic
recovery of claimed events if a publisher process crashes.
"""

import asyncio
import signal
import sys
import uuid
from collections.abc import Sequence
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


async def claim_batch(
    batch_size: int | None = None,
    lease_seconds: int | None = None,
    publisher_id: str | None = None,
    session: AsyncSession | None = None,
) -> Sequence[OutboxEvent]:
    """
    Atomically claim a batch of eligible events by transitioning them to CLAIMED with a lease.
    The database transaction is committed immediately, releasing row locks before network I/O.
    """
    b_size = batch_size if batch_size is not None else settings.OUTBOX_PUBLISHER_BATCH_SIZE
    l_secs = lease_seconds if lease_seconds is not None else settings.OUTBOX_PUBLISHER_LEASE_SECONDS
    pub_id = publisher_id or f"publisher-{uuid.uuid4().hex[:8]}"

    if session is not None:
        repo = OutboxRepository(session)
        events = await repo.claim_events(limit=b_size, lease_seconds=l_secs, claim_owner=pub_id)
        await session.commit()
        return events

    async with publisher_session_factory() as s:
        repo = OutboxRepository(s)
        events = await repo.claim_events(limit=b_size, lease_seconds=l_secs, claim_owner=pub_id)
        await s.commit()
        return events


async def publish_single_event(
    event: OutboxEvent,
    claim_owner: str,
    session: AsyncSession | None = None,
) -> bool:
    """
    Dispatch an event to RabbitMQ (outside database transaction) and settle its status in PostgreSQL.
    Verifies that the settling publisher still holds an active, unexpired claim before updating state.
    Returns True on successful dispatch and settlement, False otherwise.
    """
    event_id = event.id
    event_type = str(event.event_type)
    aggregate_id = str(event.aggregate_id)
    attempt_count = event.attempt_count

    # 1. Dispatch to RabbitMQ outside any active DB claim transaction
    try:
        _dispatch_event(event)
    except Exception as e:
        err_msg = str(e) or type(e).__name__
        logger.error(
            "outbox_event_publish_failed",
            outbox_id=str(event_id),
            claim_owner=claim_owner,
            attempt=attempt_count + 1,
            error=err_msg,
        )
        if session is not None:
            try:
                await session.rollback()
            except Exception:
                pass
            repo = OutboxRepository(session)
            failed_event = await repo.record_failure(
                event_id=event_id,
                error_message=err_msg,
                claim_owner=claim_owner,
            )
            await session.commit()
            if failed_event is None:
                logger.warning(
                    "outbox_record_failure_lost_ownership",
                    outbox_id=str(event_id),
                    claim_owner=claim_owner,
                )
        else:
            async with publisher_session_factory() as fail_session:
                try:
                    repo = OutboxRepository(fail_session)
                    failed_event = await repo.record_failure(
                        event_id=event_id,
                        error_message=err_msg,
                        claim_owner=claim_owner,
                    )
                    await fail_session.commit()
                    if failed_event is None:
                        logger.warning(
                            "outbox_record_failure_lost_ownership",
                            outbox_id=str(event_id),
                            claim_owner=claim_owner,
                        )
                except Exception as record_err:
                    logger.error(
                        "failed_to_record_outbox_failure",
                        outbox_id=str(event_id),
                        claim_owner=claim_owner,
                        error=str(record_err),
                    )
                    await fail_session.rollback()
        return False

    # 2. Settle successful publication in PostgreSQL
    if session is not None:
        repo = OutboxRepository(session)
        settled_event = await repo.mark_published(event_id=event_id, claim_owner=claim_owner)
        await session.commit()
        if settled_event is None:
            logger.warning(
                "outbox_mark_published_lost_ownership",
                outbox_id=str(event_id),
                claim_owner=claim_owner,
            )
            return False
        logger.info(
            "outbox_event_published",
            outbox_id=str(event_id),
            claim_owner=claim_owner,
            event_type=event_type,
            aggregate_id=aggregate_id,
        )
        return True
    else:
        async with publisher_session_factory() as succ_session:
            try:
                repo = OutboxRepository(succ_session)
                settled_event = await repo.mark_published(event_id=event_id, claim_owner=claim_owner)
                await succ_session.commit()
                if settled_event is None:
                    logger.warning(
                        "outbox_mark_published_lost_ownership",
                        outbox_id=str(event_id),
                        claim_owner=claim_owner,
                    )
                    return False
                logger.info(
                    "outbox_event_published",
                    outbox_id=str(event_id),
                    claim_owner=claim_owner,
                    event_type=event_type,
                    aggregate_id=aggregate_id,
                )
                return True
            except Exception as commit_err:
                logger.error(
                    "failed_to_mark_outbox_published",
                    outbox_id=str(event_id),
                    claim_owner=claim_owner,
                    error=str(commit_err),
                )
                await succ_session.rollback()
                return False


async def publish_pending_events(
    batch_size: int | None = None,
    lease_seconds: int | None = None,
    publisher_id: str | None = None,
) -> int:
    """
    Claim and publish a batch of eligible events.
    Returns the count of successfully published events.
    """
    b_size = batch_size if batch_size is not None else settings.OUTBOX_PUBLISHER_BATCH_SIZE
    l_secs = lease_seconds if lease_seconds is not None else settings.OUTBOX_PUBLISHER_LEASE_SECONDS
    pub_id = publisher_id or f"publisher-{uuid.uuid4().hex[:8]}"

    events = await claim_batch(batch_size=b_size, lease_seconds=l_secs, publisher_id=pub_id)
    if not events:
        return 0

    logger.info("outbox_events_claimed", count=len(events), publisher_id=pub_id)
    published_count = 0
    for event in events:
        success = await publish_single_event(
            event=event,
            claim_owner=pub_id,
        )
        if success:
            published_count += 1

    return published_count


async def run_publisher_loop(
    poll_interval: float | None = None,
    batch_size: int | None = None,
    lease_seconds: int | None = None,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Run continuous publisher polling loop with configurable intervals and graceful shutdown."""
    interval = poll_interval if poll_interval is not None else settings.OUTBOX_PUBLISHER_POLL_INTERVAL_SECONDS
    b_size = batch_size if batch_size is not None else settings.OUTBOX_PUBLISHER_BATCH_SIZE
    l_secs = lease_seconds if lease_seconds is not None else settings.OUTBOX_PUBLISHER_LEASE_SECONDS
    stop = stop_event or asyncio.Event()
    pub_id = f"publisher-{uuid.uuid4().hex[:8]}"

    logger.info(
        "outbox_publisher_service_started",
        publisher_id=pub_id,
        poll_interval=interval,
        batch_size=b_size,
        lease_seconds=l_secs,
    )

    while not stop.is_set():
        try:
            published = await publish_pending_events(
                batch_size=b_size,
                lease_seconds=l_secs,
                publisher_id=pub_id,
            )
            if published == 0:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=interval)
                except asyncio.TimeoutError:
                    pass
        except Exception as e:
            logger.error("outbox_publisher_loop_error", error=str(e))
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    logger.info("outbox_publisher_service_stopped", publisher_id=pub_id)


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
        asyncio.run(run_publisher_loop(stop_event=stop_event))
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
