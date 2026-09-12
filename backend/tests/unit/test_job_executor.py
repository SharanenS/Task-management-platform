"""Unit tests for asynchronous job execution engine."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.constants import JobStatus
from app.models.job import Job
from app.tasks.executor import execute_job_by_id


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def sample_queued_job():
    return Job(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        job_type="REPORT_GENERATION",
        status=JobStatus.QUEUED,
        payload={"report_type": "summary"},
        error_message=None,
    )


@pytest.mark.asyncio
async def test_execute_job_success(mock_session, sample_queued_job):
    """Successful execution transitions QUEUED -> PROCESSING (via atomic claim) -> COMPLETED (fenced)."""
    processing_job = Job(
        id=sample_queued_job.id,
        project_id=sample_queued_job.project_id,
        job_type=sample_queued_job.job_type,
        status=JobStatus.PROCESSING,
        payload=sample_queued_job.payload,
        error_message=None,
        execution_claim_owner="test-worker",
    )
    completed_job = Job(
        id=sample_queued_job.id,
        project_id=sample_queued_job.project_id,
        job_type=sample_queued_job.job_type,
        status=JobStatus.COMPLETED,
        payload=sample_queued_job.payload,
        error_message=None,
    )

    with (
        patch("app.tasks.executor.worker_session_factory") as mock_factory,
        patch("app.tasks.executor.JobRepository"),
        patch("app.tasks.executor.ProjectRepository"),
        patch("app.tasks.executor.JobService") as mock_job_service_cls,
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session
        job_service = mock_job_service_cls.return_value
        job_service.claim_job = AsyncMock(return_value=processing_job)
        job_service.complete_job = AsyncMock(return_value=completed_job)

        await execute_job_by_id(sample_queued_job.id)

        assert job_service.claim_job.call_count == 1
        claim_args = job_service.claim_job.call_args
        assert claim_args[0][0] == sample_queued_job.id or claim_args[1].get("job_id") == sample_queued_job.id
        job_service.complete_job.assert_called_once()
        complete_args = job_service.complete_job.call_args
        assert complete_args[0][0] == sample_queued_job.id
        # Commit called twice: 1) immediately after atomic claim, 2) after fenced completion
        assert mock_session.commit.call_count == 2


@pytest.mark.asyncio
async def test_execute_job_handler_failure(mock_session, sample_queued_job):
    """Handler failure transitions QUEUED -> PROCESSING (claimed) -> FAILED (fenced) with error_message."""
    processing_job = Job(
        id=sample_queued_job.id,
        project_id=sample_queued_job.project_id,
        job_type=sample_queued_job.job_type,
        status=JobStatus.PROCESSING,
        payload={"simulate_failure": True, "error_message": "Database write error"},
        error_message=None,
        execution_claim_owner="test-worker",
    )
    failed_job = Job(
        id=sample_queued_job.id,
        project_id=sample_queued_job.project_id,
        job_type=sample_queued_job.job_type,
        status=JobStatus.FAILED,
        payload=processing_job.payload,
        error_message="Database write error",
    )

    with (
        patch("app.tasks.executor.worker_session_factory") as mock_factory,
        patch("app.tasks.executor.JobRepository"),
        patch("app.tasks.executor.ProjectRepository"),
        patch("app.tasks.executor.JobService") as mock_job_service_cls,
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session
        job_service = mock_job_service_cls.return_value
        job_service.claim_job = AsyncMock(return_value=processing_job)
        job_service.fail_job = AsyncMock(return_value=failed_job)

        await execute_job_by_id(sample_queued_job.id)

        assert job_service.claim_job.call_count == 1
        job_service.fail_job.assert_called_once()
        fail_args = job_service.fail_job.call_args
        assert fail_args[0][0] == sample_queued_job.id
        error_msg = fail_args[1].get("error_message") or fail_args[0][2]
        assert "Database write error" in error_msg


@pytest.mark.asyncio
async def test_execute_job_unknown_type(mock_session, sample_queued_job):
    """Unknown job_type transitions to FAILED via fenced fail_job."""
    processing_job = Job(
        id=sample_queued_job.id,
        project_id=sample_queued_job.project_id,
        job_type="NON_EXISTENT_TYPE",
        status=JobStatus.PROCESSING,
        payload=None,
        error_message=None,
        execution_claim_owner="test-worker",
    )

    with (
        patch("app.tasks.executor.worker_session_factory") as mock_factory,
        patch("app.tasks.executor.JobRepository"),
        patch("app.tasks.executor.ProjectRepository"),
        patch("app.tasks.executor.JobService") as mock_job_service_cls,
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session
        job_service = mock_job_service_cls.return_value
        job_service.claim_job = AsyncMock(return_value=processing_job)
        job_service.fail_job = AsyncMock()

        await execute_job_by_id(sample_queued_job.id)

        assert job_service.claim_job.call_count == 1
        job_service.fail_job.assert_called_once()
        fail_args = job_service.fail_job.call_args
        assert fail_args[0][0] == sample_queued_job.id
        error_msg = fail_args[1].get("error_message") or fail_args[0][2]
        assert "Unknown or unsupported job type" in error_msg


@pytest.mark.asyncio
async def test_execute_job_missing_job(mock_session):
    """Non-existent job is logged and skipped safely without errors."""
    with (
        patch("app.tasks.executor.worker_session_factory") as mock_factory,
        patch("app.tasks.executor.JobRepository") as mock_job_repo_cls,
        patch("app.tasks.executor.JobService") as mock_job_service_cls,
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session
        job_repo = mock_job_repo_cls.return_value
        job_repo.get_by_id = AsyncMock(return_value=None)
        job_service = mock_job_service_cls.return_value
        job_service.claim_job = AsyncMock(return_value=None)

        await execute_job_by_id(uuid.uuid4())

        assert job_service.complete_job.call_count == 0
        assert job_service.fail_job.call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_status", [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.PROCESSING])
async def test_execute_job_terminal_or_processing_is_skipped(mock_session, sample_queued_job, terminal_status):
    """Jobs that cannot be claimed because already terminal (COMPLETED/FAILED) or in-flight (PROCESSING) are skipped."""
    sample_queued_job.status = terminal_status

    with (
        patch("app.tasks.executor.worker_session_factory") as mock_factory,
        patch("app.tasks.executor.JobRepository") as mock_job_repo_cls,
        patch("app.tasks.executor.JobService") as mock_job_service_cls,
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session
        job_repo = mock_job_repo_cls.return_value
        job_repo.get_by_id = AsyncMock(return_value=sample_queued_job)
        job_service = mock_job_service_cls.return_value
        # Atomic claim fails because job is not in QUEUED status
        job_service.claim_job = AsyncMock(return_value=None)

        await execute_job_by_id(sample_queued_job.id)

        assert job_service.claim_job.call_count == 1
        assert job_service.complete_job.call_count == 0
        assert job_service.fail_job.call_count == 0
