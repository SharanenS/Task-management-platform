"""Integration test for PostgreSQL atomic claiming concurrency."""

import asyncio
import uuid
import pytest

from app.core.constants import JobStatus, ProjectStatus
from app.db.session import async_session_factory
from app.models.job import Job
from app.models.project import Project
from app.repositories.job import JobRepository


@pytest.mark.asyncio
async def test_real_postgresql_concurrent_claim_job():
    """
    Focused PostgreSQL-backed concurrency verification:
    Proves that when two concurrent workers attempt to claim the exact same QUEUED job,
    only one worker successfully transitions the job to PROCESSING and receives the updated Job,
    while the other worker receives None.
    Also verifies:
    - Winner has status == PROCESSING
    - Winner has updated_at populated
    - Third claim attempt on already-claimed job returns None
    """
    project_id = uuid.uuid4()
    job_id = uuid.uuid4()

    # 1. Insert a Project and QUEUED Job into PostgreSQL
    async with async_session_factory() as session:
        proj = Project(
            id=project_id,
            name=f"PG Concurrency Test {project_id.hex[:6]}",
            status=ProjectStatus.ACTIVE,
            owner_id="test-pg-concurrency-owner",
        )
        session.add(proj)

        job = Job(
            id=job_id,
            project_id=project_id,
            job_type="REPORT_GENERATION",
            status=JobStatus.QUEUED,
            payload={"report_type": "summary"},
            error_message=None,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        initial_updated_at = job.updated_at

    await asyncio.sleep(0.02)

    # 2. Concurrently attempt to claim the same job from two separate database sessions
    worker_results: list[Job | None] = [None, None]

    async def worker_attempt(index: int) -> None:
        async with async_session_factory() as worker_session:
            repo = JobRepository(worker_session)
            claimed = await repo.claim_job(job_id)
            if claimed:
                await worker_session.commit()
            worker_results[index] = claimed

    await asyncio.gather(worker_attempt(0), worker_attempt(1))

    res0, res1 = worker_results

    # 3. Assert exactly one worker succeeded
    assert (res0 is not None) ^ (res1 is not None), (
        f"Concurrency failure: expected exactly one successful claim, got res0={res0}, res1={res1}"
    )

    winner = res0 if res0 is not None else res1
    loser = res1 if res0 is not None else res0

    assert loser is None
    assert winner.id == job_id
    assert winner.status == JobStatus.PROCESSING
    assert winner.updated_at is not None
    assert winner.updated_at >= initial_updated_at

    # 4. Verify durable database state in fresh session
    async with async_session_factory() as verify_session:
        repo_verify = JobRepository(verify_session)
        persisted = await repo_verify.get_by_id(job_id)
        assert persisted is not None
        assert persisted.status == JobStatus.PROCESSING

        # 5. Subsequent claim attempt on now-PROCESSING job returns None
        subsequent_claim = await repo_verify.claim_job(job_id)
        assert subsequent_claim is None
