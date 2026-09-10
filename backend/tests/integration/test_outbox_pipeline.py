"""Integration tests for Phase 8 Transactional Outbox Publisher & Lease/Claim Mechanism.

Tests run against real PostgreSQL and RabbitMQ instances.
Verifies:
1. Job + Outbox persistence in a single database transaction.
2. Atomicity on rollback.
3. Concurrent publisher claim partitioning with FOR UPDATE SKIP LOCKED.
4. Lease expiration recovery.
5. Network I/O decoupled from PostgreSQL row locks.
6. Broker failure recovery and pending retry state.
7. End-to-end Job creation -> Outbox claim -> RabbitMQ -> Worker execution -> Job COMPLETED.
8. Duplicate message delivery idempotency.
9. Stale publisher settlement rejection (ownership race prevention).
10. Unclaimed expired lease settlement rejection.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.constants import JobStatus, OutboxEventType, OutboxStatus, ProjectStatus
from app.models.job import Job
from app.models.outbox import OutboxEvent
from app.models.project import Project
from app.repositories.job import JobRepository
from app.repositories.outbox import OutboxRepository
from app.repositories.project import ProjectRepository
from app.schemas.job import JobCreate
from app.services.job import JobService
from app.tasks.executor import execute_job_by_id
from app.tasks.outbox_publisher import (
    claim_batch,
    publish_pending_events,
    publish_single_event,
)


@pytest.fixture
async def db_factory():
    """Per-test NullPool async session factory avoiding cross-event-loop connection reuse."""
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
async def real_project_id(db_factory):
    """Create a real active Project in PostgreSQL for integration testing."""
    pid = uuid.uuid4()
    async with db_factory() as session:
        proj = Project(
            id=pid,
            name=f"Outbox Integration Project {pid.hex[:6]}",
            status=ProjectStatus.ACTIVE,
            owner_id="outbox-tester",
        )
        session.add(proj)
        await session.commit()
    return pid


@pytest.mark.asyncio
async def test_job_and_outbox_persisted_in_single_transaction(db_factory, real_project_id):
    """
    Core Invariant Test:
    Creating a Job via JobService creates both Job (QUEUED) and OutboxEvent (PENDING)
    in the same database session, which are committed together in one PostgreSQL commit.
    """
    async with db_factory() as session:
        job_repo = JobRepository(session)
        project_repo = ProjectRepository(session)
        outbox_repo = OutboxRepository(session)
        service = JobService(
            repository=job_repo,
            project_repository=project_repo,
            outbox_repository=outbox_repo,
        )

        job = await service.create_job(
            JobCreate(
                project_id=real_project_id,
                job_type="REPORT_GENERATION",
                payload={"report_type": "quarterly"},
            )
        )
        await session.commit()
        job_id = job.id

    # Verify both exist durably in PostgreSQL in a fresh session
    async with db_factory() as verify_session:
        db_job = (
            await verify_session.execute(select(Job).where(Job.id == job_id))
        ).scalar_one_or_none()
        assert db_job is not None
        assert db_job.status == JobStatus.QUEUED

        db_outbox = (
            await verify_session.execute(
                select(OutboxEvent).where(
                    OutboxEvent.aggregate_id == job_id,
                    OutboxEvent.aggregate_type == "JOB",
                )
            )
        ).scalar_one_or_none()
        assert db_outbox is not None
        assert db_outbox.status == OutboxStatus.PENDING
        assert db_outbox.event_type == OutboxEventType.JOB_CREATED
        assert db_outbox.payload == {"job_id": str(job_id)}
        assert db_outbox.attempt_count == 0


@pytest.mark.asyncio
async def test_job_and_outbox_rollback_together_on_commit_failure(db_factory, real_project_id):
    """
    Core Invariant Test:
    If transaction rollback occurs before commit, NEITHER the Job NOR the OutboxEvent persists.
    """
    simulated_job_id = None
    async with db_factory() as session:
        job_repo = JobRepository(session)
        project_repo = ProjectRepository(session)
        outbox_repo = OutboxRepository(session)
        service = JobService(
            repository=job_repo,
            project_repository=project_repo,
            outbox_repository=outbox_repo,
        )

        job = await service.create_job(
            JobCreate(
                project_id=real_project_id,
                job_type="REPORT_GENERATION",
                payload={"test": "rollback"},
            )
        )
        simulated_job_id = job.id
        await session.rollback()

    # Verify neither was persisted to PostgreSQL
    async with db_factory() as verify_session:
        db_job = (
            await verify_session.execute(select(Job).where(Job.id == simulated_job_id))
        ).scalar_one_or_none()
        assert db_job is None

        db_outbox = (
            await verify_session.execute(
                select(OutboxEvent).where(OutboxEvent.aggregate_id == simulated_job_id)
            )
        ).scalar_one_or_none()
        assert db_outbox is None


@pytest.mark.asyncio
async def test_concurrent_publishers_skip_locked(db_factory, real_project_id):
    """
    Concurrency Invariant:
    Two concurrent publisher async tasks claiming events with FOR UPDATE SKIP LOCKED
    claim disjoint partitions and establish active leases without collision.
    """
    event_ids = []
    # Clean only non-settled events to isolate concurrency test deterministically
    async with db_factory() as session:
        await session.execute(
            delete(OutboxEvent).where(OutboxEvent.status.in_([OutboxStatus.PENDING, OutboxStatus.CLAIMED]))
        )
        for _ in range(4):
            jid = uuid.uuid4()
            event = OutboxEvent(
                id=uuid.uuid4(),
                event_type=OutboxEventType.JOB_CREATED,
                aggregate_type="JOB",
                aggregate_id=jid,
                payload={"job_id": str(jid)},
                status=OutboxStatus.PENDING,
            )
            session.add(event)
            event_ids.append(event.id)
        await session.commit()

    a_locked_event = asyncio.Event()
    b_finished_event = asyncio.Event()

    async def publisher_task_a():
        async with db_factory() as session_a:
            repo_a = OutboxRepository(session_a)
            claimed_a = await repo_a.claim_events(limit=2, lease_seconds=30, claim_owner="pub-A")
            ids = [e.id for e in claimed_a]
            a_locked_event.set()
            await b_finished_event.wait()
            await session_a.commit()
            return ids

    async def publisher_task_b():
        await a_locked_event.wait()
        async with db_factory() as session_b:
            repo_b = OutboxRepository(session_b)
            claimed_b = await repo_b.claim_events(limit=2, lease_seconds=30, claim_owner="pub-B")
            ids = [e.id for e in claimed_b]
            b_finished_event.set()
            await session_b.commit()
            return ids

    claimed_a, claimed_b = await asyncio.gather(publisher_task_a(), publisher_task_b())

    # Verify exact partition: no overlap, each claimed 2, union covers all 4
    assert len(claimed_a) == 2, f"Publisher A expected 2 events, got {len(claimed_a)}"
    assert len(claimed_b) == 2, f"Publisher B expected 2 events, got {len(claimed_b)}"
    overlap = set(claimed_a).intersection(set(claimed_b))
    assert len(overlap) == 0, f"Found unexpected overlapping claims: {overlap}"
    assert set(claimed_a).union(set(claimed_b)) == set(event_ids)

    # Verify rows in PostgreSQL are now CLAIMED with valid lease_until and claim_owner
    async with db_factory() as verify_session:
        rows = (
            await verify_session.execute(
                select(OutboxEvent).where(OutboxEvent.id.in_(event_ids))
            )
        ).scalars().all()
        for r in rows:
            assert r.status == OutboxStatus.CLAIMED
            assert r.lease_until is not None
            assert r.claim_owner in {"pub-A", "pub-B"}


@pytest.mark.asyncio
async def test_claim_and_lease_expiration_recovery(db_factory, real_project_id):
    """
    Lease Expiration & Recovery Invariant:
    1. Publisher A claims an event with a 1-second lease and crashes (abandons it).
    2. While lease is active, Publisher B cannot claim it.
    3. Once lease expires, Publisher B successfully claims and publishes the event.
    """
    jid = uuid.uuid4()
    eid = uuid.uuid4()

    async with db_factory() as session:
        event = OutboxEvent(
            id=eid,
            event_type=OutboxEventType.JOB_CREATED,
            aggregate_type="JOB",
            aggregate_id=jid,
            payload={"job_id": str(jid)},
            status=OutboxStatus.PENDING,
        )
        session.add(event)
        await session.commit()

    # 1. Publisher A claims with 1-second lease
    async with db_factory() as session_a:
        repo_a = OutboxRepository(session_a)
        claimed = await repo_a.claim_events(limit=50, lease_seconds=1, claim_owner="pub-crashed")
        target = next((e for e in claimed if e.id == eid), None)
        assert target is not None
        await session_a.commit()

    # 2. Publisher B immediately attempts to claim (lease is still active)
    async with db_factory() as session_b:
        repo_b = OutboxRepository(session_b)
        active_claimed = await repo_b.claim_events(limit=50, lease_seconds=30, claim_owner="pub-survivor")
        reclaimed_target = next((e for e in active_claimed if e.id == eid), None)
        assert reclaimed_target is None, "Expected active lease to prevent claim"
        await session_b.commit()

    # 3. Wait for lease to expire
    await asyncio.sleep(1.1)

    # 4. Publisher B attempts to claim again after lease expiration -> successfully reclaims
    async with db_factory() as session_b:
        repo_b = OutboxRepository(session_b)
        recovered = await repo_b.claim_events(limit=50, lease_seconds=30, claim_owner="pub-survivor")
        reclaimed_target = next((e for e in recovered if e.id == eid), None)
        assert reclaimed_target is not None
        assert reclaimed_target.claim_owner == "pub-survivor"
        await session_b.commit()


@pytest.mark.asyncio
async def test_network_io_outside_db_row_locks(db_factory, real_project_id):
    """
    Decoupled Architecture Test:
    Proves the claim transaction commits before dispatch, ensuring NO PostgreSQL
    row locks are held while performing RabbitMQ network I/O.
    """
    jid = uuid.uuid4()
    eid = uuid.uuid4()

    async with db_factory() as session:
        event = OutboxEvent(
            id=eid,
            event_type=OutboxEventType.JOB_CREATED,
            aggregate_type="JOB",
            aggregate_id=jid,
            payload={"job_id": str(jid)},
            status=OutboxStatus.PENDING,
        )
        session.add(event)
        await session.commit()

    # Publisher claims batch
    claimed = await claim_batch(batch_size=50, lease_seconds=30, publisher_id="pub-decoupled")
    target = next((e for e in claimed if e.id == eid), None)
    assert target is not None

    # In an independent session, verify row is not locked by attempting FOR UPDATE NOWAIT
    async with db_factory() as verify_session:
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.id == eid)
            .with_for_update(nowait=True)
        )
        # If locks were held, nowait=True would raise OperationalError
        row = (await verify_session.execute(stmt)).scalar_one()
        assert row.status == OutboxStatus.CLAIMED
        assert row.claim_owner == "pub-decoupled"


@pytest.mark.asyncio
async def test_broker_failure_leaves_outbox_pending_and_recoverable(db_factory, real_project_id):
    """
    Failure Behavior Test:
    When broker publication raises an exception:
    - Job remains QUEUED
    - Outbox is reset to PENDING and lease cleared
    - attempt_count increments
    - last_error is recorded
    - event is not deleted and remains recoverable
    """
    job_id = uuid.uuid4()
    event_id = uuid.uuid4()

    async with db_factory() as session:
        job = Job(
            id=job_id,
            project_id=real_project_id,
            job_type="REPORT_GENERATION",
            status=JobStatus.QUEUED,
            payload={"job_id": str(job_id)},
        )
        event = OutboxEvent(
            id=event_id,
            event_type=OutboxEventType.JOB_CREATED,
            aggregate_type="JOB",
            aggregate_id=job_id,
            payload={"job_id": str(job_id)},
            status=OutboxStatus.CLAIMED,
            attempt_count=0,
            lease_until=datetime.now(timezone.utc) + text_interval(30),
            claim_owner="pub-err",
        )
        session.add(job)
        session.add(event)
        await session.commit()

    # Simulate broker failure during publication attempt
    with patch("app.tasks.jobs.process_job_task.delay", side_effect=RuntimeError("RabbitMQ broker connection timed out")):
        async with db_factory() as pub_session:
            ev = (
                await pub_session.execute(
                    select(OutboxEvent).where(OutboxEvent.id == event_id)
                )
            ).scalar_one()
            success = await publish_single_event(
                event=ev,
                claim_owner="pub-err",
                session=pub_session,
            )
            assert success is False

    # Verify both Job and OutboxEvent state in PostgreSQL
    async with db_factory() as verify_session:
        db_job = (
            await verify_session.execute(select(Job).where(Job.id == job_id))
        ).scalar_one_or_none()
        assert db_job is not None
        assert db_job.status == JobStatus.QUEUED

        repo = OutboxRepository(verify_session)
        updated_event = await repo.get_by_id(event_id)
        assert updated_event is not None
        assert updated_event.status == OutboxStatus.PENDING
        assert updated_event.lease_until is None
        assert updated_event.claim_owner is None
        assert updated_event.attempt_count == 1
        assert "RabbitMQ broker connection timed out" in (updated_event.last_error or "")
        assert updated_event.published_at is None


def text_interval(seconds: int):
    from datetime import timedelta
    return timedelta(seconds=seconds)


@pytest.mark.asyncio
async def test_end_to_end_outbox_to_worker_pipeline(db_factory, real_project_id):
    """
    Full End-to-End Test:
    1. Create Job + OutboxEvent in PostgreSQL.
    2. Publisher claims batch with lease.
    3. Publisher dispatches to real RabbitMQ outside DB transaction.
    4. Settle event as PUBLISHED in PostgreSQL.
    5. Verify task exists in RabbitMQ.
    6. Worker receives task, atomically claims QUEUED -> PROCESSING, executes, transitions to COMPLETED.
    """
    # 1. Create Job + OutboxEvent
    async with db_factory() as session:
        job_repo = JobRepository(session)
        project_repo = ProjectRepository(session)
        outbox_repo = OutboxRepository(session)
        service = JobService(
            repository=job_repo,
            project_repository=project_repo,
            outbox_repository=outbox_repo,
        )

        job = await service.create_job(
            JobCreate(
                project_id=real_project_id,
                job_type="REPORT_GENERATION",
                payload={"report_type": "annual_financials"},
            )
        )
        await session.commit()
        job_id = job.id

    # Clean queue before test
    with celery_app.connection_for_write() as conn:
        with conn.channel() as channel:
            try:
                channel.queue_purge("celery")
            except Exception:
                pass

    # 2. Claim event with lease
    claimed = await claim_batch(batch_size=50, lease_seconds=30, publisher_id="pub-e2e")
    target_event = next((e for e in claimed if e.aggregate_id == job_id), None)
    assert target_event is not None, f"Event for job {job_id} was not claimed in batch"

    # 3 & 4. Publish event outside claim transaction with explicit claim ownership
    success = await publish_single_event(
        event=target_event,
        claim_owner="pub-e2e",
    )
    assert success is True

    # Verify outbox event became PUBLISHED in PostgreSQL with cleared lease
    async with db_factory() as verify_session:
        outbox = (
            await verify_session.execute(
                select(OutboxEvent).where(OutboxEvent.aggregate_id == job_id)
            )
        ).scalar_one_or_none()
        assert outbox is not None
        assert outbox.status == OutboxStatus.PUBLISHED
        assert outbox.published_at is not None
        assert outbox.lease_until is None
        assert outbox.claim_owner is None

    # 5. Verify task physically landed in RabbitMQ queue
    with celery_app.connection_for_read() as conn:
        with conn.channel() as channel:
            _, msg_count, _ = channel.queue_declare("celery", passive=True)
            assert msg_count >= 1

    # 6. Worker executes job
    await execute_job_by_id(job_id)

    # Verify job reached COMPLETED in PostgreSQL
    async with db_factory() as verify_session:
        completed_job = (
            await verify_session.execute(select(Job).where(Job.id == job_id))
        ).scalar_one_or_none()
        assert completed_job is not None
        assert completed_job.status == JobStatus.COMPLETED
        assert completed_job.error_message is None


@pytest.mark.asyncio
async def test_duplicate_task_delivery_is_idempotent(db_factory, real_project_id):
    """
    Duplicate Delivery Test:
    At-least-once outbox publication can deliver the same job ID more than once.
    The Phase 6 atomic claim ensures the second execution attempt is safely skipped.
    """
    async with db_factory() as session:
        job_repo = JobRepository(session)
        project_repo = ProjectRepository(session)
        outbox_repo = OutboxRepository(session)
        service = JobService(
            repository=job_repo,
            project_repository=project_repo,
            outbox_repository=outbox_repo,
        )

        job = await service.create_job(
            JobCreate(
                project_id=real_project_id,
                job_type="REPORT_GENERATION",
                payload={"report_type": "idempotency_check"},
            )
        )
        await session.commit()
        job_id = job.id

    # First worker execution consumes and completes the job
    await execute_job_by_id(job_id)

    async with db_factory() as verify_session:
        first_state = (
            await verify_session.execute(select(Job).where(Job.id == job_id))
        ).scalar_one()
        assert first_state.status == JobStatus.COMPLETED
        first_updated_at = first_state.updated_at

    # Second duplicate task delivery executes again with the same Job ID
    await execute_job_by_id(job_id)

    # Job remains COMPLETED and was not re-executed
    async with db_factory() as verify_session:
        second_state = (
            await verify_session.execute(select(Job).where(Job.id == job_id))
        ).scalar_one()
        assert second_state.status == JobStatus.COMPLETED
        assert second_state.updated_at == first_updated_at


@pytest.mark.asyncio
async def test_stale_publisher_settlement_rejected_after_reclaim(db_factory, real_project_id):
    """
    Critical Race Semantics Test:
    1. Publisher A claims event with claim_owner='pub-A' and a 1s lease.
    2. Simulate lease expiry / ownership change to Publisher B ('pub-B').
    3. Publisher A attempts mark_published -> rejected (0 rows updated, returns None).
    4. Verify Publisher A cannot change Publisher B's CLAIMED event.
    5. Publisher A attempts record_failure -> rejected (0 rows updated, returns None).
    6. Verify Publisher B can still settle its own claim.
    7. Verify stale publisher failure cannot clear B's lease or reset status to PENDING.
    """
    jid = uuid.uuid4()
    eid = uuid.uuid4()

    async with db_factory() as session:
        event = OutboxEvent(
            id=eid,
            event_type=OutboxEventType.JOB_CREATED,
            aggregate_type="JOB",
            aggregate_id=jid,
            payload={"job_id": str(jid)},
            status=OutboxStatus.PENDING,
        )
        session.add(event)
        await session.commit()

    # 1. Publisher A claims event with 1-second lease
    async with db_factory() as session_a:
        repo_a = OutboxRepository(session_a)
        claimed_a = await repo_a.claim_events(limit=50, lease_seconds=1, claim_owner="pub-A")
        target_a = next((e for e in claimed_a if e.id == eid), None)
        assert target_a is not None
        assert target_a.claim_owner == "pub-A"
        await session_a.commit()

    # 2. Simulate lease expiry while Publisher A is blocked
    await asyncio.sleep(1.1)

    # Publisher B reclaims the expired event with 30-second lease
    async with db_factory() as session_b:
        repo_b = OutboxRepository(session_b)
        claimed_b = await repo_b.claim_events(limit=50, lease_seconds=30, claim_owner="pub-B")
        target_b = next((e for e in claimed_b if e.id == eid), None)
        assert target_b is not None
        assert target_b.claim_owner == "pub-B"
        await session_b.commit()

    # Capture Publisher B's lease state
    async with db_factory() as verify_session:
        db_b = (
            await verify_session.execute(select(OutboxEvent).where(OutboxEvent.id == eid))
        ).scalar_one()
        assert db_b.status == OutboxStatus.CLAIMED
        assert db_b.claim_owner == "pub-B"
        b_lease_until = db_b.lease_until

    # 3 & 4. Publisher A attempts mark_published -> rejected, cannot mutate B's CLAIMED event
    async with db_factory() as session_a:
        repo_a = OutboxRepository(session_a)
        settle_result = await repo_a.mark_published(event_id=eid, claim_owner="pub-A")
        assert settle_result is None, "Stale publisher A must not be allowed to mark event as published"
        await session_a.commit()

    # Verify Publisher B's active claim remains unchanged
    async with db_factory() as verify_session:
        db_after_a_publish = (
            await verify_session.execute(select(OutboxEvent).where(OutboxEvent.id == eid))
        ).scalar_one()
        assert db_after_a_publish.status == OutboxStatus.CLAIMED
        assert db_after_a_publish.claim_owner == "pub-B"
        assert db_after_a_publish.lease_until == b_lease_until
        assert db_after_a_publish.published_at is None

    # 5. Publisher A attempts record_failure -> rejected, cannot clear B's lease or reset status to PENDING
    async with db_factory() as session_a:
        repo_a = OutboxRepository(session_a)
        fail_result = await repo_a.record_failure(
            event_id=eid,
            error_message="Stale publisher network timeout",
            claim_owner="pub-A",
        )
        assert fail_result is None, "Stale publisher A must not be allowed to record failure on B's claim"
        await session_a.commit()

    # Verify Publisher B's active claim remains completely untouched (NOT reset to PENDING, lease NOT cleared)
    async with db_factory() as verify_session:
        db_after_a_fail = (
            await verify_session.execute(select(OutboxEvent).where(OutboxEvent.id == eid))
        ).scalar_one()
        assert db_after_a_fail.status == OutboxStatus.CLAIMED
        assert db_after_a_fail.claim_owner == "pub-B"
        assert db_after_a_fail.lease_until == b_lease_until
        assert db_after_a_fail.attempt_count == 0
        assert db_after_a_fail.last_error is None

    # 6. Publisher B settles its own claim -> succeeds
    async with db_factory() as session_b:
        repo_b = OutboxRepository(session_b)
        b_settle_result = await repo_b.mark_published(event_id=eid, claim_owner="pub-B")
        assert b_settle_result is not None
        assert b_settle_result.status == OutboxStatus.PUBLISHED
        assert b_settle_result.claim_owner is None
        assert b_settle_result.lease_until is None
        assert b_settle_result.published_at is not None
        await session_b.commit()

    # Final verification: event is legitimately PUBLISHED
    async with db_factory() as verify_session:
        final_event = (
            await verify_session.execute(select(OutboxEvent).where(OutboxEvent.id == eid))
        ).scalar_one()
        assert final_event.status == OutboxStatus.PUBLISHED
        assert final_event.claim_owner is None
        assert final_event.lease_until is None


@pytest.mark.asyncio
async def test_stale_publisher_cannot_settle_after_own_lease_expires_even_if_unclaimed(db_factory, real_project_id):
    """
    Lease Expiry Guard Test:
    Even if no other publisher has reclaimed the event yet, a publisher whose lease expired
    cannot settle the event because lease_until >= now() fails.
    """
    jid = uuid.uuid4()
    eid = uuid.uuid4()

    async with db_factory() as session:
        event = OutboxEvent(
            id=eid,
            event_type=OutboxEventType.JOB_CREATED,
            aggregate_type="JOB",
            aggregate_id=jid,
            payload={"job_id": str(jid)},
            status=OutboxStatus.PENDING,
        )
        session.add(event)
        await session.commit()

    # Publisher A claims with 1-second lease
    async with db_factory() as session_a:
        repo_a = OutboxRepository(session_a)
        claimed = await repo_a.claim_events(limit=50, lease_seconds=1, claim_owner="pub-A")
        target = next((e for e in claimed if e.id == eid), None)
        assert target is not None
        await session_a.commit()

    # Wait for lease to expire without another publisher reclaiming
    await asyncio.sleep(1.1)

    # Publisher A attempts mark_published after lease expired
    async with db_factory() as session_a:
        repo_a = OutboxRepository(session_a)
        settle_result = await repo_a.mark_published(event_id=eid, claim_owner="pub-A")
        assert settle_result is None, "Expired lease must reject settlement"
        await session_a.commit()

    # Event remains CLAIMED with expired lease, safely awaitable for reclamation
    async with db_factory() as verify_session:
        db_event = (
            await verify_session.execute(select(OutboxEvent).where(OutboxEvent.id == eid))
        ).scalar_one()
        assert db_event.status == OutboxStatus.CLAIMED
        assert db_event.claim_owner == "pub-A"
        assert db_event.published_at is None
