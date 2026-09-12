"""Unit tests for Phase 10 Job Recovery background daemon."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.job import Job
from app.tasks.job_recovery import (
    reclaim_batch,
    recover_and_dispatch_jobs,
)


@pytest.fixture
def sample_reclaimed_job():
    return Job(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        job_type="REPORT_GENERATION",
        status="PROCESSING",
        payload={"report_type": "summary"},
        error_message=None,
        execution_claim_owner="recovery-unit-test",
    )


@pytest.mark.asyncio
async def test_reclaim_batch_success(sample_reclaimed_job):
    """reclaim_batch opens session, calls repo.reclaim_expired_jobs, and commits."""
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    with (
        patch("app.tasks.job_recovery.recovery_session_factory") as mock_factory,
        patch("app.tasks.job_recovery.JobRepository") as mock_repo_cls,
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_repo = mock_repo_cls.return_value
        mock_repo.reclaim_expired_jobs = AsyncMock(return_value=[sample_reclaimed_job])

        jobs = await reclaim_batch(batch_size=10, lease_seconds=300, recovery_id="rec-1")

        assert len(jobs) == 1
        assert jobs[0] == sample_reclaimed_job
        mock_repo.reclaim_expired_jobs.assert_called_once_with(
            limit=10,
            claim_owner="rec-1",
            lease_seconds=300,
        )
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_recover_and_dispatch_jobs_empty():
    """When no expired jobs exist, recover_and_dispatch_jobs returns 0 without Celery dispatch."""
    with (
        patch("app.tasks.job_recovery.reclaim_batch", new_callable=AsyncMock) as mock_reclaim,
        patch("app.tasks.job_recovery.process_job_task.delay") as mock_celery,
    ):
        mock_reclaim.return_value = []

        count = await recover_and_dispatch_jobs(batch_size=10, lease_seconds=300, recovery_id="rec-1")

        assert count == 0
        mock_reclaim.assert_called_once_with(
            batch_size=10,
            lease_seconds=300,
            recovery_id="rec-1",
        )
        mock_celery.assert_not_called()


@pytest.mark.asyncio
async def test_recover_and_dispatch_jobs_success(sample_reclaimed_job):
    """Reclaimed jobs are dispatched to Celery with recovery claim owner after DB commit."""
    with (
        patch("app.tasks.job_recovery.reclaim_batch", new_callable=AsyncMock) as mock_reclaim,
        patch("app.tasks.job_recovery.process_job_task.delay") as mock_celery,
    ):
        mock_reclaim.return_value = [sample_reclaimed_job]

        count = await recover_and_dispatch_jobs(batch_size=5, lease_seconds=300, recovery_id="rec-1")

        assert count == 1
        mock_celery.assert_called_once_with(str(sample_reclaimed_job.id), claim_owner="rec-1")
