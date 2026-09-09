"""Unit tests for asynchronous job executor and handlers."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.constants import JobStatus
from app.models.job import Job
from app.tasks.executor import execute_job_by_id
from app.tasks.handlers import (
    get_handler,
    handle_cleanup,
    handle_data_export,
    handle_report_generation,
)


# ── Handler Unit Tests ──────────────────────────────────────────────────────

def test_report_generation_handler_success():
    result = handle_report_generation({"report_type": "monthly"})
    assert result["status"] == "success"
    assert result["report_type"] == "monthly"
    assert result["records_processed"] == 100


def test_report_generation_handler_failure():
    with pytest.raises(ValueError, match="data corruption detected"):
        handle_report_generation({"simulate_failure": True})


def test_data_export_handler_success():
    result = handle_data_export({"format": "parquet"})
    assert result["status"] == "success"
    assert result["format"] == "parquet"
    assert result["rows_exported"] == 500


def test_data_export_handler_failure():
    with pytest.raises(ValueError, match="disk quota exceeded"):
        handle_data_export({"simulate_failure": True})


def test_cleanup_handler_success():
    result = handle_cleanup({"retention_days": 60})
    assert result["status"] == "success"
    assert result["cleaned_items"] == 15


def test_cleanup_handler_failure():
    with pytest.raises(ValueError, match="permission denied"):
        handle_cleanup({"simulate_failure": True})


def test_unknown_handler_returns_none():
    assert get_handler("UNKNOWN_TYPE_XYZ") is None


# ── Executor Flow Tests ─────────────────────────────────────────────────────

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
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_execute_job_success(mock_session, sample_queued_job):
    """Successful execution transitions QUEUED -> PROCESSING (via atomic claim) -> COMPLETED."""
    processing_job = Job(
        id=sample_queued_job.id,
        project_id=sample_queued_job.project_id,
        job_type=sample_queued_job.job_type,
        status=JobStatus.PROCESSING,
        payload=sample_queued_job.payload,
        error_message=None,
        created_at=sample_queued_job.created_at,
        updated_at=datetime.now(timezone.utc),
    )
    completed_job = Job(
        id=sample_queued_job.id,
        project_id=sample_queued_job.project_id,
        job_type=sample_queued_job.job_type,
        status=JobStatus.COMPLETED,
        payload=sample_queued_job.payload,
        error_message=None,
        created_at=sample_queued_job.created_at,
        updated_at=datetime.now(timezone.utc),
    )

    with (
        patch("app.tasks.executor.worker_session_factory") as mock_factory,
        patch("app.tasks.executor.JobRepository") as mock_job_repo_cls,
        patch("app.tasks.executor.ProjectRepository"),
        patch("app.tasks.executor.JobService") as mock_job_service_cls,
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session
        job_service = mock_job_service_cls.return_value
        job_service.claim_job = AsyncMock(return_value=processing_job)
        job_service.update_status = AsyncMock(return_value=completed_job)

        await execute_job_by_id(sample_queued_job.id)

        job_service.claim_job.assert_called_once_with(sample_queued_job.id)
        job_service.update_status.assert_called_once()
        status_arg = job_service.update_status.call_args[0][1]
        assert status_arg.status == JobStatus.COMPLETED
        # Commit called twice: 1) immediately after atomic claim, 2) after completion
        assert mock_session.commit.call_count == 2


@pytest.mark.asyncio
async def test_execute_job_handler_failure(mock_session, sample_queued_job):
    """Handler failure transitions QUEUED -> PROCESSING (claimed) -> FAILED with error_message."""
    processing_job = Job(
        id=sample_queued_job.id,
        project_id=sample_queued_job.project_id,
        job_type=sample_queued_job.job_type,
        status=JobStatus.PROCESSING,
        payload={"simulate_failure": True, "error_message": "Database write error"},
        error_message=None,
        created_at=sample_queued_job.created_at,
        updated_at=datetime.now(timezone.utc),
    )
    failed_job = Job(
        id=sample_queued_job.id,
        project_id=sample_queued_job.project_id,
        job_type=sample_queued_job.job_type,
        status=JobStatus.FAILED,
        payload=processing_job.payload,
        error_message="Database write error",
        created_at=sample_queued_job.created_at,
        updated_at=datetime.now(timezone.utc),
    )

    with (
        patch("app.tasks.executor.worker_session_factory") as mock_factory,
        patch("app.tasks.executor.JobRepository") as mock_job_repo_cls,
        patch("app.tasks.executor.ProjectRepository"),
        patch("app.tasks.executor.JobService") as mock_job_service_cls,
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session
        job_service = mock_job_service_cls.return_value
        job_service.claim_job = AsyncMock(return_value=processing_job)
        job_service.update_status = AsyncMock(return_value=failed_job)

        await execute_job_by_id(sample_queued_job.id)

        job_service.claim_job.assert_called_once_with(sample_queued_job.id)
        job_service.update_status.assert_called_once()
        status_arg = job_service.update_status.call_args[0][1]
        assert status_arg.status == JobStatus.FAILED
        assert "Database write error" in status_arg.error_message


@pytest.mark.asyncio
async def test_execute_job_unknown_type(mock_session, sample_queued_job):
    """Unknown job_type transitions to FAILED with informative error message."""
    processing_job = Job(
        id=sample_queued_job.id,
        project_id=sample_queued_job.project_id,
        job_type="NON_EXISTENT_TYPE",
        status=JobStatus.PROCESSING,
        payload=None,
        error_message=None,
        created_at=sample_queued_job.created_at,
        updated_at=datetime.now(timezone.utc),
    )

    with (
        patch("app.tasks.executor.worker_session_factory") as mock_factory,
        patch("app.tasks.executor.JobRepository") as mock_job_repo_cls,
        patch("app.tasks.executor.ProjectRepository"),
        patch("app.tasks.executor.JobService") as mock_job_service_cls,
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session
        job_service = mock_job_service_cls.return_value
        job_service.claim_job = AsyncMock(return_value=processing_job)
        job_service.update_status = AsyncMock()

        await execute_job_by_id(sample_queued_job.id)

        job_service.claim_job.assert_called_once_with(sample_queued_job.id)
        job_service.update_status.assert_called_once()
        status_arg = job_service.update_status.call_args[0][1]
        assert status_arg.status == JobStatus.FAILED
        assert "Unknown or unsupported job type" in status_arg.error_message


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

        assert job_service.update_status.call_count == 0


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

        job_service.claim_job.assert_called_once_with(sample_queued_job.id)
        assert job_service.update_status.call_count == 0
