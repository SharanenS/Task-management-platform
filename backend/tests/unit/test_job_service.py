"""Unit tests for JobService, JobRepository, and Job schemas."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.core.constants import JobStatus, ProjectStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.job import Job
from app.models.project import Project
from app.core.constants import OutboxEventType, OutboxStatus
from app.repositories.job import JobRepository
from app.repositories.outbox import OutboxRepository
from app.repositories.project import ProjectRepository
from app.schemas.job import JobCreate, JobStatusUpdate
from app.services.job import JobService


@pytest.fixture
def mock_job_repo():
    return AsyncMock(spec=JobRepository)


@pytest.fixture
def mock_project_repo():
    return AsyncMock(spec=ProjectRepository)


@pytest.fixture
def mock_outbox_repo():
    return AsyncMock(spec=OutboxRepository)


@pytest.fixture
def service(mock_job_repo, mock_project_repo, mock_outbox_repo):
    return JobService(
        repository=mock_job_repo,
        project_repository=mock_project_repo,
        outbox_repository=mock_outbox_repo,
    )


@pytest.fixture
def sample_project():
    return Project(
        id=uuid.uuid4(),
        name="Test Project",
        description="Project for testing jobs",
        status=ProjectStatus.ACTIVE,
        owner_id="keycloak-user-123",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_job(sample_project):
    return Job(
        id=uuid.uuid4(),
        project_id=sample_project.id,
        job_type="REPORT_GENERATION",
        status=JobStatus.QUEUED,
        payload={"format": "pdf"},
        error_message=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


# ── Creation Tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_job_success(service, mock_job_repo, mock_project_repo, mock_outbox_repo, sample_project):
    mock_project_repo.get_by_id.return_value = sample_project

    data = JobCreate(
        project_id=sample_project.id,
        job_type="DATA_EXPORT",
        payload={"tables": ["users", "projects"]},
    )

    created_job = Job(
        id=uuid.uuid4(),
        project_id=sample_project.id,
        job_type="DATA_EXPORT",
        status=JobStatus.QUEUED,
        payload={"tables": ["users", "projects"]},
        error_message=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_job_repo.create.return_value = created_job

    result = await service.create_job(data)

    assert result.project_id == sample_project.id
    assert result.job_type == "DATA_EXPORT"
    assert result.status == JobStatus.QUEUED
    assert result.payload == {"tables": ["users", "projects"]}
    assert result.error_message is None
    mock_project_repo.get_by_id.assert_called_once_with(sample_project.id)
    mock_job_repo.create.assert_called_once()

    # Verify transactional outbox event creation
    mock_outbox_repo.create.assert_called_once()
    outbox_event = mock_outbox_repo.create.call_args[0][0]
    assert outbox_event.event_type == OutboxEventType.JOB_CREATED
    assert outbox_event.aggregate_type == "JOB"
    assert outbox_event.aggregate_id == created_job.id
    assert outbox_event.payload == {"job_id": str(created_job.id)}
    assert outbox_event.status == OutboxStatus.PENDING


@pytest.mark.asyncio
async def test_create_job_nonexistent_project_raises_404(service, mock_project_repo):
    mock_project_repo.get_by_id.return_value = None
    random_project_id = uuid.uuid4()

    data = JobCreate(
        project_id=random_project_id,
        job_type="DATA_EXPORT",
    )

    with pytest.raises(NotFoundError) as exc_info:
        await service.create_job(data)

    assert f"Project with ID '{random_project_id}' not found" in str(exc_info.value)


# ── Retrieval Tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_job_found(service, mock_job_repo, sample_job):
    mock_job_repo.get_by_id.return_value = sample_job

    result = await service.get_job(sample_job.id)

    assert result == sample_job
    mock_job_repo.get_by_id.assert_called_once_with(sample_job.id)


@pytest.mark.asyncio
async def test_get_job_not_found_raises_404(service, mock_job_repo):
    mock_job_repo.get_by_id.return_value = None
    random_id = uuid.uuid4()

    with pytest.raises(NotFoundError) as exc_info:
        await service.get_job(random_id)

    assert f"Job with ID '{random_id}' not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_list_jobs_by_project_success(service, mock_job_repo, mock_project_repo, sample_project, sample_job):
    mock_project_repo.get_by_id.return_value = sample_project
    mock_job_repo.list_by_project.return_value = [sample_job]

    result = await service.list_jobs(sample_project.id)

    assert len(result) == 1
    assert result[0] == sample_job
    mock_project_repo.get_by_id.assert_called_once_with(sample_project.id)
    mock_job_repo.list_by_project.assert_called_once_with(sample_project.id)


@pytest.mark.asyncio
async def test_list_jobs_nonexistent_project_raises_404(service, mock_project_repo):
    mock_project_repo.get_by_id.return_value = None
    random_project_id = uuid.uuid4()

    with pytest.raises(NotFoundError) as exc_info:
        await service.list_jobs(random_project_id)

    assert f"Project with ID '{random_project_id}' not found" in str(exc_info.value)


# ── Lifecycle State Transition Tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_transition_queued_to_processing(service, mock_job_repo, sample_job):
    sample_job.status = JobStatus.QUEUED
    mock_job_repo.get_by_id.return_value = sample_job
    mock_job_repo.update.return_value = sample_job

    update_data = JobStatusUpdate(status=JobStatus.PROCESSING)
    result = await service.update_status(sample_job.id, update_data)

    assert result.status == JobStatus.PROCESSING
    mock_job_repo.update.assert_called_once_with(sample_job)


@pytest.mark.asyncio
async def test_transition_queued_to_failed_stores_error_message(service, mock_job_repo, sample_job):
    sample_job.status = JobStatus.QUEUED
    mock_job_repo.get_by_id.return_value = sample_job
    mock_job_repo.update.return_value = sample_job

    update_data = JobStatusUpdate(status=JobStatus.FAILED, error_message="Initialization timed out")
    result = await service.update_status(sample_job.id, update_data)

    assert result.status == JobStatus.FAILED
    assert result.error_message == "Initialization timed out"
    mock_job_repo.update.assert_called_once_with(sample_job)


@pytest.mark.asyncio
async def test_transition_processing_to_completed_clears_error(service, mock_job_repo, sample_job):
    sample_job.status = JobStatus.PROCESSING
    sample_job.error_message = "Previous error"
    mock_job_repo.get_by_id.return_value = sample_job
    mock_job_repo.update.return_value = sample_job

    update_data = JobStatusUpdate(status=JobStatus.COMPLETED)
    result = await service.update_status(sample_job.id, update_data)

    assert result.status == JobStatus.COMPLETED
    assert result.error_message is None
    mock_job_repo.update.assert_called_once_with(sample_job)


@pytest.mark.asyncio
async def test_transition_processing_to_failed(service, mock_job_repo, sample_job):
    sample_job.status = JobStatus.PROCESSING
    mock_job_repo.get_by_id.return_value = sample_job
    mock_job_repo.update.return_value = sample_job

    update_data = JobStatusUpdate(status=JobStatus.FAILED, error_message="Worker crash")
    result = await service.update_status(sample_job.id, update_data)

    assert result.status == JobStatus.FAILED
    assert result.error_message == "Worker crash"


@pytest.mark.asyncio
async def test_invalid_transitions_raise_bad_request(service, mock_job_repo, sample_job):
    invalid_cases = [
        (JobStatus.QUEUED, JobStatus.COMPLETED),
        (JobStatus.PROCESSING, JobStatus.QUEUED),
        (JobStatus.COMPLETED, JobStatus.PROCESSING),
        (JobStatus.COMPLETED, JobStatus.QUEUED),
        (JobStatus.COMPLETED, JobStatus.FAILED),
        (JobStatus.FAILED, JobStatus.PROCESSING),
        (JobStatus.FAILED, JobStatus.QUEUED),
        (JobStatus.FAILED, JobStatus.COMPLETED),
    ]

    for current, target in invalid_cases:
        sample_job.status = current
        mock_job_repo.get_by_id.return_value = sample_job

        with pytest.raises(BadRequestError) as exc_info:
            await service.update_status(sample_job.id, JobStatusUpdate(status=target))

        assert "Invalid status transition" in str(exc_info.value)


# ── Schema Whitespace Validation Tests ──────────────────────────────────────

def test_job_create_whitespace_only_type_rejected():
    with pytest.raises(Exception):
        JobCreate(project_id=uuid.uuid4(), job_type="   ")


def test_job_create_tab_only_type_rejected():
    with pytest.raises(Exception):
        JobCreate(project_id=uuid.uuid4(), job_type="\t")


def test_job_create_valid_type_trimmed():
    schema = JobCreate(project_id=uuid.uuid4(), job_type="  REPORT_GEN  ")
    assert schema.job_type == "REPORT_GEN"


# ── Atomic Claiming Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_claim_queued_job_succeeds(service, mock_job_repo, sample_job):
    """1. A QUEUED Job can be claimed successfully."""
    claimed_job = Job(
        id=sample_job.id,
        project_id=sample_job.project_id,
        job_type=sample_job.job_type,
        status=JobStatus.PROCESSING,
        payload=sample_job.payload,
        error_message=None,
        created_at=sample_job.created_at,
        updated_at=datetime.now(timezone.utc),
    )
    mock_job_repo.claim_job.return_value = claimed_job

    result = await service.claim_job(sample_job.id)

    assert result is not None
    assert result.status == JobStatus.PROCESSING
    mock_job_repo.claim_job.assert_called_once_with(sample_job.id)


@pytest.mark.asyncio
async def test_claim_processing_job_fails(service, mock_job_repo, sample_job):
    """2. A Job already in PROCESSING cannot be claimed again."""
    # Repository conditional UPDATE WHERE status = 'QUEUED' matches 0 rows and returns None
    mock_job_repo.claim_job.return_value = None

    result = await service.claim_job(sample_job.id)

    assert result is None
    mock_job_repo.claim_job.assert_called_once_with(sample_job.id)


@pytest.mark.asyncio
async def test_claim_completed_job_fails(service, mock_job_repo, sample_job):
    """3. A COMPLETED Job cannot be claimed."""
    mock_job_repo.claim_job.return_value = None

    result = await service.claim_job(sample_job.id)

    assert result is None
    mock_job_repo.claim_job.assert_called_once_with(sample_job.id)


@pytest.mark.asyncio
async def test_claim_failed_job_fails(service, mock_job_repo, sample_job):
    """4. A FAILED Job cannot be claimed."""
    mock_job_repo.claim_job.return_value = None

    result = await service.claim_job(sample_job.id)

    assert result is None
    mock_job_repo.claim_job.assert_called_once_with(sample_job.id)


@pytest.mark.asyncio
async def test_two_workers_claim_same_queued_job_only_one_succeeds(service, mock_job_repo, sample_job):
    """5. Two execution attempts cannot both successfully claim the same QUEUED Job."""
    claimed_job = Job(
        id=sample_job.id,
        project_id=sample_job.project_id,
        job_type=sample_job.job_type,
        status=JobStatus.PROCESSING,
        payload=sample_job.payload,
        error_message=None,
        created_at=sample_job.created_at,
        updated_at=datetime.now(timezone.utc),
    )
    # First attempt matches QUEUED and updates to PROCESSING; second attempt matches 0 rows
    mock_job_repo.claim_job.side_effect = [claimed_job, None]

    # Worker A attempts claim
    worker_a_result = await service.claim_job(sample_job.id)
    # Worker B attempts claim on the same job
    worker_b_result = await service.claim_job(sample_job.id)

    assert worker_a_result is not None
    assert worker_a_result.status == JobStatus.PROCESSING
    assert worker_b_result is None
    assert mock_job_repo.claim_job.call_count == 2
