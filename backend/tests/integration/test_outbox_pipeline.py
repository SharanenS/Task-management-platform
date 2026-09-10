"""Integration tests for Phase 7 Transactional Outbox pipeline with real PostgreSQL and RabbitMQ."""

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
        # Explicit rollback simulates failure
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
    Two concurrent publisher queries using FOR UPDATE SKIP LOCKED claim disjoint subsets
    without blocking or deadlocking while locks are held simultaneously.
    """
    event_ids = []
    # Seed isolated batch of pending outbox events
    async with db_factory() as session:
        await session.execute(delete(OutboxEvent))
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

    # Simulate two concurrent publisher async tasks claiming batches simultaneously
    a_locked_event = asyncio.Event()
    b_finished_event = asyncio.Event()

    async def publisher_task_a():
        async with db_factory() as session_a:
            repo_a = OutboxRepository(session_a)
            # Publisher A claims 2 rows and holds row locks in open transaction
            batch_a = await repo_a.get_pending_events(limit=2)
            claimed = [e.id for e in batch_a]
            # Signal that Publisher A is actively holding row locks
            a_locked_event.set()
            # Wait until Publisher B has queried PostgreSQL while locks are held
            await b_finished_event.wait()
            return claimed

    async def publisher_task_b():
        # Wait until Publisher A has acquired row locks
        await a_locked_event.wait()
        async with db_factory() as session_b:
            repo_b = OutboxRepository(session_b)
            # Publisher B queries while Publisher A's transaction is actively open and holding locks
            batch_b = await repo_b.get_pending_events(limit=2)
            claimed = [e.id for e in batch_b]
            # Signal that Publisher B has finished querying
            b_finished_event.set()
            return claimed

    claimed_a, claimed_b = await asyncio.gather(publisher_task_a(), publisher_task_b())

    # Verify exact partition: no overlap, each claimed 2, union covers all 4
    assert len(claimed_a) == 2, f"Publisher A expected 2 events, got {len(claimed_a)}"
    assert len(claimed_b) == 2, f"Publisher B expected 2 events, got {len(claimed_b)}"
    overlap = set(claimed_a).intersection(set(claimed_b))
    assert len(overlap) == 0, f"Found unexpected overlapping claims: {overlap}"
    assert set(claimed_a).union(set(claimed_b)) == set(event_ids)


@pytest.mark.asyncio
async def test_broker_failure_leaves_outbox_pending_and_recoverable(db_factory, real_project_id):
    """
    Failure Behavior Test:
    When broker publication raises an exception:
    - Job remains QUEUED
    - Outbox remains PENDING
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
            status=OutboxStatus.PENDING,
            attempt_count=0,
        )
        session.add(job)
        session.add(event)
        await session.commit()

    # Simulate broker failure during publication attempt
    with patch("app.tasks.jobs.process_job_task.delay", side_effect=RuntimeError("RabbitMQ broker connection timed out")):
        async with db_factory() as pub_session:
            repo = OutboxRepository(pub_session)
            ev = await repo.get_by_id(event_id)
            success = await publish_single_event(pub_session, ev)
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
        assert updated_event.attempt_count == 1
        assert "RabbitMQ broker connection timed out" in (updated_event.last_error or "")
        assert updated_event.published_at is None


@pytest.mark.asyncio
async def test_end_to_end_outbox_to_worker_pipeline(db_factory, real_project_id):
    """
    Full End-to-End Test:
    1. Create Job + OutboxEvent in PostgreSQL.
    2. Publisher claims PENDING event, dispatches to real RabbitMQ, updates Outbox to PUBLISHED.
    3. Verify task exists in RabbitMQ.
    4. Worker receives task, atomically claims QUEUED -> PROCESSING, executes, transitions to COMPLETED.
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

    # 2. Publish outbox event to RabbitMQ
    async with db_factory() as pub_session:
        ev = (
            await pub_session.execute(
                select(OutboxEvent).where(OutboxEvent.aggregate_id == job_id)
            )
        ).scalar_one()
        success = await publish_single_event(pub_session, ev)
        assert success is True

    # Verify outbox event became PUBLISHED in PostgreSQL
    async with db_factory() as verify_session:
        outbox = (
            await verify_session.execute(
                select(OutboxEvent).where(OutboxEvent.aggregate_id == job_id)
            )
        ).scalar_one_or_none()
        assert outbox is not None
        assert outbox.status == OutboxStatus.PUBLISHED
        assert outbox.published_at is not None

    # Verify task physically landed in RabbitMQ queue
    with celery_app.connection_for_read() as conn:
        with conn.channel() as channel:
            _, msg_count, _ = channel.queue_declare("celery", passive=True)
            assert msg_count >= 1

    # 3. Worker executes job
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
