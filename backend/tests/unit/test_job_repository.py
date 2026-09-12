"""Unit tests for JobRepository Phase 10 leasing and fencing methods."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import JobStatus
from app.models.job import Job
from app.repositories.job import JobRepository


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def repo(mock_session):
    return JobRepository(mock_session)


@pytest.fixture
def sample_job():
    return Job(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        job_type="REPORT_GENERATION",
        status=JobStatus.QUEUED,
        payload={"report_type": "summary"},
        error_message=None,
        processing_started_at=None,
        execution_lease_until=None,
        execution_claim_owner=None,
    )


@pytest.mark.asyncio
async def test_claim_job_establishes_owner_and_lease(repo, mock_session, sample_job):
    sample_job.status = JobStatus.PROCESSING
    sample_job.execution_claim_owner = "worker-1"
    sample_job.execution_lease_until = datetime.now(timezone.utc)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_job
    mock_session.execute.return_value = mock_result

    claimed = await repo.claim_job(sample_job.id, claim_owner="worker-1", lease_seconds=300)

    assert claimed is not None
    assert claimed.status == JobStatus.PROCESSING
    assert claimed.execution_claim_owner == "worker-1"
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_reclaim_expired_jobs_empty(repo, mock_session):
    mock_select_res = MagicMock()
    mock_select_scalars = MagicMock()
    mock_select_scalars.all.return_value = []
    mock_select_res.scalars.return_value = mock_select_scalars
    mock_session.execute.return_value = mock_select_res

    reclaimed = await repo.reclaim_expired_jobs(limit=10, claim_owner="recovery-1", lease_seconds=300)

    assert len(reclaimed) == 0
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_reclaim_expired_jobs_success(repo, mock_session, sample_job):
    sample_job.status = JobStatus.PROCESSING
    sample_job.execution_claim_owner = "recovery-1"
    sample_job.execution_lease_until = datetime.now(timezone.utc)

    mock_select_res = MagicMock()
    mock_select_scalars = MagicMock()
    mock_select_scalars.all.return_value = [sample_job]
    mock_select_res.scalars.return_value = mock_select_scalars

    mock_update_res = MagicMock()
    mock_update_scalars = MagicMock()
    mock_update_scalars.all.return_value = [sample_job]
    mock_update_res.scalars.return_value = mock_update_scalars

    mock_session.execute.side_effect = [mock_select_res, mock_update_res]

    reclaimed = await repo.reclaim_expired_jobs(limit=10, claim_owner="recovery-1", lease_seconds=300)

    assert len(reclaimed) == 1
    assert reclaimed[0].execution_claim_owner == "recovery-1"
    assert mock_session.execute.call_count == 2


@pytest.mark.asyncio
async def test_complete_job_fenced_success(repo, mock_session, sample_job):
    sample_job.status = JobStatus.COMPLETED
    sample_job.execution_claim_owner = None
    sample_job.execution_lease_until = None
    sample_job.processing_started_at = None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_job
    mock_session.execute.return_value = mock_result

    completed = await repo.complete_job(sample_job.id, claim_owner="worker-1")

    assert completed is not None
    assert completed.status == JobStatus.COMPLETED
    assert completed.execution_claim_owner is None
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_complete_job_fenced_rejects_stale_owner(repo, mock_session, sample_job):
    """When claim owner does not match or lease expired, 0 rows match and returns None."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    completed = await repo.complete_job(sample_job.id, claim_owner="stale-worker")

    assert completed is None
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_fail_job_fenced_success(repo, mock_session, sample_job):
    sample_job.status = JobStatus.FAILED
    sample_job.error_message = "Handler exception"
    sample_job.execution_claim_owner = None
    sample_job.execution_lease_until = None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_job
    mock_session.execute.return_value = mock_result

    failed = await repo.fail_job(sample_job.id, claim_owner="worker-1", error_message="Handler exception")

    assert failed is not None
    assert failed.status == JobStatus.FAILED
    assert failed.error_message == "Handler exception"
    assert failed.execution_claim_owner is None
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_fail_job_fenced_rejects_stale_owner(repo, mock_session, sample_job):
    """When claim owner does not match or lease expired, fail_job returns None."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    failed = await repo.fail_job(sample_job.id, claim_owner="stale-worker", error_message="Handler exception")

    assert failed is None
    mock_session.execute.assert_called_once()
