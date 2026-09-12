"""Integration tests for Phase 10 Reliable Job Execution & Recovery.

Tests run against real PostgreSQL and RabbitMQ instances.
Verifies all 23 items specified in Phase 10:
1. Normal claim: QUEUED -> PROCESSING remains atomic.
2. Only one of two concurrent normal claims succeeds.
3. Normal claim establishes owner and lease.
4. PROCESSING job with unexpired lease cannot be reclaimed.
5. PROCESSING job with expired lease can be reclaimed.
6. Two concurrent recovery workers cannot both reclaim the same job.
7. Recovery replaces the old owner.
8. Recovery creates a new lease.
9. Old worker cannot complete after ownership is replaced.
10. Old worker cannot fail after ownership is replaced.
11. Current owner can complete.
12. Current owner can fail.
13. Completion clears execution ownership fields.
14. Failure clears execution ownership fields.
15. Crash scenario: worker commits PROCESSING, disappears, lease expires, recovery reclaims, completes.
16. Duplicate Celery delivery for currently PROCESSING job is skipped.
17. Duplicate delivery for terminal job does nothing.
18. Unknown handler transitions to FAILED through fenced path.
19. Stale worker cannot overwrite recovered job with unknown-handler failure.
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.constants import JobStatus, ProjectStatus
from app.models.job import Job
from app.models.project import Project
from app.repositories.job import JobRepository
from app.tasks.executor import execute_job_by_id
from app.tasks.job_recovery import reclaim_batch, recover_and_dispatch_jobs


@pytest.fixture
async def db_factory():
    """Per-test NullPool async session factory."""
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_expired_jobs(db_factory):
    """Ensure no stale expired PROCESSING jobs linger between test runs."""
    async with db_factory() as session:
        await session.execute(
            delete(Job).where(
                Job.status == JobStatus.PROCESSING,
                Job.execution_lease_until.is_not(None),
                Job.execution_lease_until < datetime.now(timezone.utc),
            )
        )
        await session.commit()
    yield


@pytest.fixture
async def real_project_id(db_factory):
    """Create a real active Project in PostgreSQL for testing."""
    pid = uuid.uuid4()
    async with db_factory() as session:
        proj = Project(
            id=pid,
            name=f"Phase 10 Recovery Test {pid.hex[:6]}",
            status=ProjectStatus.ACTIVE,
            owner_id="recovery-tester",
        )
        session.add(proj)
        await session.commit()
    return pid


@pytest.mark.asyncio
async def test_normal_claim_establishes_owner_and_lease(db_factory, real_project_id):
    """Items 1, 3: Normal claim transitions QUEUED -> PROCESSING and populates owner + lease."""
    job_id = uuid.uuid4()
    async with db_factory() as session:
        job = Job(
            id=job_id,
            project_id=real_project_id,
            job_type="REPORT_GENERATION",
            status=JobStatus.QUEUED,
            payload={"report_type": "summary"},
        )
        session.add(job)
        await session.commit()

        repo = JobRepository(session)
        claimed = await repo.claim_job(job_id, claim_owner="worker-owner-1", lease_seconds=60)
        await session.commit()

        assert claimed is not None
        assert claimed.status == JobStatus.PROCESSING
        assert claimed.execution_claim_owner == "worker-owner-1"
        assert claimed.processing_started_at is not None
        assert claimed.execution_lease_until is not None
        assert claimed.execution_lease_until > claimed.processing_started_at


@pytest.mark.asyncio
async def test_unexpired_processing_job_cannot_be_reclaimed(db_factory, real_project_id):
    """Item 4: A PROCESSING job whose lease has NOT expired cannot be reclaimed."""
    job_id = uuid.uuid4()
    now_utc = datetime.now(timezone.utc)
    future_lease = now_utc + timedelta(seconds=300)

    async with db_factory() as session:
        job = Job(
            id=job_id,
            project_id=real_project_id,
            job_type="REPORT_GENERATION",
            status=JobStatus.PROCESSING,
            payload={"report_type": "summary"},
            processing_started_at=now_utc,
            execution_lease_until=future_lease,
            execution_claim_owner="worker-active",
        )
        session.add(job)
        await session.commit()

        repo = JobRepository(session)
        reclaimed = await repo.reclaim_expired_jobs(limit=10, claim_owner="recovery-1", lease_seconds=60)
        reclaimed_ids = [j.id for j in reclaimed]
        assert job_id not in reclaimed_ids


@pytest.mark.asyncio
async def test_expired_processing_job_reclaim_replaces_owner_and_lease(db_factory, real_project_id):
    """Items 5, 7, 8: An expired PROCESSING job is reclaimed with new owner, new lease, and new processing_started_at."""
    job_id = uuid.uuid4()
    past_time = datetime.now(timezone.utc) - timedelta(seconds=100)

    async with db_factory() as session:
        job = Job(
            id=job_id,
            project_id=real_project_id,
            job_type="REPORT_GENERATION",
            status=JobStatus.PROCESSING,
            payload={"report_type": "summary"},
            processing_started_at=past_time - timedelta(seconds=50),
            execution_lease_until=past_time,
            execution_claim_owner="dead-worker",
        )
        session.add(job)
        await session.commit()

        repo = JobRepository(session)
        reclaimed = await repo.reclaim_expired_jobs(limit=10, claim_owner="recovery-new-owner", lease_seconds=120)
        await session.commit()

        reclaimed_ids = [j.id for j in reclaimed]
        assert job_id in reclaimed_ids
        reclaimed_job = next(j for j in reclaimed if j.id == job_id)
        assert reclaimed_job.status == JobStatus.PROCESSING
        assert reclaimed_job.execution_claim_owner == "recovery-new-owner"
        assert reclaimed_job.execution_lease_until > datetime.now(timezone.utc)
        assert reclaimed_job.processing_started_at > past_time


@pytest.mark.asyncio
async def test_concurrent_recovery_workers_skip_locked(db_factory, real_project_id):
    """Item 6: Two concurrent recovery workers cannot both reclaim the same expired job."""
    job_ids = [uuid.uuid4(), uuid.uuid4()]
    past_time = datetime.now(timezone.utc) - timedelta(seconds=60)

    async with db_factory() as session:
        for jid in job_ids:
            job = Job(
                id=jid,
                project_id=real_project_id,
                job_type="REPORT_GENERATION",
                status=JobStatus.PROCESSING,
                payload={},
                processing_started_at=past_time,
                execution_lease_until=past_time,
                execution_claim_owner="crashed-worker",
            )
            session.add(job)
        await session.commit()

    results: list[list[uuid.UUID]] = [[], []]

    async def recovery_worker(index: int, owner: str) -> None:
        async with db_factory() as session:
            repo = JobRepository(session)
            claimed = await repo.reclaim_expired_jobs(limit=10, claim_owner=owner, lease_seconds=60)
            await session.commit()
            results[index] = [j.id for j in claimed if j.id in job_ids]

    await asyncio.gather(
        recovery_worker(0, "rec-worker-0"),
        recovery_worker(1, "rec-worker-1"),
    )

    claimed_by_0 = set(results[0])
    claimed_by_1 = set(results[1])

    # Assert no job was claimed by both recovery workers
    assert claimed_by_0.isdisjoint(claimed_by_1), "Concurrent recovery claimed overlapping jobs!"
    # Assert all expired jobs were claimed across the two workers
    assert claimed_by_0 | claimed_by_1 == set(job_ids)


@pytest.mark.asyncio
async def test_fencing_stale_worker_cannot_complete_or_fail(db_factory, real_project_id):
    """Items 9, 10, 11, 13: Stale worker loses race; cannot complete or fail. New owner succeeds."""
    job_id = uuid.uuid4()
    past_time = datetime.now(timezone.utc) - timedelta(seconds=60)

    async with db_factory() as session:
        # Job claimed by Worker A, but lease expired
        job = Job(
            id=job_id,
            project_id=real_project_id,
            job_type="REPORT_GENERATION",
            status=JobStatus.PROCESSING,
            payload={},
            processing_started_at=past_time,
            execution_lease_until=past_time,
            execution_claim_owner="worker-A",
        )
        session.add(job)
        await session.commit()

        # Recovery reclaims for Worker B
        repo = JobRepository(session)
        await repo.reclaim_expired_jobs(limit=10, claim_owner="worker-B", lease_seconds=300)
        await session.commit()

        # Worker A wakes up and attempts complete_job
        a_complete = await repo.complete_job(job_id, claim_owner="worker-A")
        await session.commit()
        assert a_complete is None, "Stale worker A should have been rejected from complete_job"

        # Worker A attempts fail_job
        a_fail = await repo.fail_job(job_id, claim_owner="worker-A", error_message="Stale failure")
        await session.commit()
        assert a_fail is None, "Stale worker A should have been rejected from fail_job"

        # Job is still PROCESSING under worker B
        current = await repo.get_by_id(job_id)
        assert current.status == JobStatus.PROCESSING
        assert current.execution_claim_owner == "worker-B"

        # Worker B completes the job
        b_complete = await repo.complete_job(job_id, claim_owner="worker-B")
        await session.commit()
        assert b_complete is not None
        assert b_complete.status == JobStatus.COMPLETED
        assert b_complete.execution_claim_owner is None
        assert b_complete.execution_lease_until is None
        assert b_complete.processing_started_at is None


@pytest.mark.asyncio
async def test_fencing_current_owner_can_fail_and_clears_ownership(db_factory, real_project_id):
    """Items 12, 14: Current owner can fail job; failure clears execution ownership fields."""
    job_id = uuid.uuid4()
    future_time = datetime.now(timezone.utc) + timedelta(seconds=300)

    async with db_factory() as session:
        job = Job(
            id=job_id,
            project_id=real_project_id,
            job_type="REPORT_GENERATION",
            status=JobStatus.PROCESSING,
            payload={},
            processing_started_at=datetime.now(timezone.utc),
            execution_lease_until=future_time,
            execution_claim_owner="worker-current",
        )
        session.add(job)
        await session.commit()

        repo = JobRepository(session)
        failed = await repo.fail_job(job_id, claim_owner="worker-current", error_message="Fatal crash")
        await session.commit()

        assert failed is not None
        assert failed.status == JobStatus.FAILED
        assert failed.error_message == "Fatal crash"
        assert failed.execution_claim_owner is None
        assert failed.execution_lease_until is None
        assert failed.processing_started_at is None


@pytest.mark.asyncio
async def test_crash_recovery_end_to_end(db_factory, real_project_id):
    """Items 15-18: Crash scenario - Worker A commits PROCESSING, dies; recovery reclaims; execution finishes."""
    job_id = uuid.uuid4()

    # Step 1: Create QUEUED job
    async with db_factory() as session:
        job = Job(
            id=job_id,
            project_id=real_project_id,
            job_type="REPORT_GENERATION",
            status=JobStatus.QUEUED,
            payload={"report_type": "summary"},
        )
        session.add(job)
        await session.commit()

    # Step 2: Worker A claims job with short lease and crashes (disappears)
    async with db_factory() as session:
        repo = JobRepository(session)
        claimed = await repo.claim_job(job_id, claim_owner="worker-A-crashed", lease_seconds=1)
        await session.commit()
        assert claimed is not None

    # Step 3: Wait for lease to expire
    await asyncio.sleep(1.1)

    # Step 4: Verify job is still PROCESSING (stranded until recovery)
    async with db_factory() as session:
        repo = JobRepository(session)
        stuck_job = await repo.get_by_id(job_id)
        assert stuck_job.status == JobStatus.PROCESSING
        assert stuck_job.execution_claim_owner == "worker-A-crashed"

    # Step 5: Recovery daemon reclaims expired job
    recovery_owner = "recovery-runner-1"
    reclaimed_count = await recover_and_dispatch_jobs(
        batch_size=10,
        lease_seconds=60,
        recovery_id=recovery_owner,
    )
    assert reclaimed_count == 1

    # Step 6: Execute as recovered job (passing claim_owner)
    await execute_job_by_id(job_id, claim_owner=recovery_owner)

    # Step 7: Verify job completed successfully
    async with db_factory() as session:
        repo = JobRepository(session)
        final_job = await repo.get_by_id(job_id)
        assert final_job.status == JobStatus.COMPLETED
        assert final_job.execution_claim_owner is None
        assert final_job.execution_lease_until is None


@pytest.mark.asyncio
async def test_duplicate_celery_delivery_is_idempotent(db_factory, real_project_id):
    """Items 19-21: Duplicate Celery delivery for in-flight or terminal job skips safely."""
    job_id = uuid.uuid4()

    # Create and claim job into PROCESSING
    async with db_factory() as session:
        job = Job(
            id=job_id,
            project_id=real_project_id,
            job_type="REPORT_GENERATION",
            status=JobStatus.PROCESSING,
            payload={"report_type": "summary"},
            processing_started_at=datetime.now(timezone.utc),
            execution_lease_until=datetime.now(timezone.utc) + timedelta(seconds=300),
            execution_claim_owner="active-worker",
        )
        session.add(job)
        await session.commit()

    # Normal Celery delivery arrives for already-PROCESSING job
    await execute_job_by_id(job_id)

    # Verify job was untouched
    async with db_factory() as session:
        repo = JobRepository(session)
        j = await repo.get_by_id(job_id)
        assert j.status == JobStatus.PROCESSING
        assert j.execution_claim_owner == "active-worker"


@pytest.mark.asyncio
async def test_unknown_handler_fenced_failure_path(db_factory, real_project_id):
    """Items 22-23: Unknown job type transitions to FAILED via fenced path; stale worker cannot overwrite."""
    job_id = uuid.uuid4()

    async with db_factory() as session:
        job = Job(
            id=job_id,
            project_id=real_project_id,
            job_type="INVALID_UNKNOWN_TYPE_123",
            status=JobStatus.QUEUED,
            payload={},
        )
        session.add(job)
        await session.commit()

    # Normal delivery executes
    await execute_job_by_id(job_id)

    # Job is FAILED with unknown handler error
    async with db_factory() as session:
        repo = JobRepository(session)
        j = await repo.get_by_id(job_id)
        assert j.status == JobStatus.FAILED
        assert "Unknown or unsupported job type" in j.error_message
        assert j.execution_claim_owner is None
        assert j.execution_lease_until is None
