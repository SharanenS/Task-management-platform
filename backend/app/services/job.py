"""Service layer for Job business logic and lifecycle state transitions."""

import uuid
from collections.abc import Sequence

from app.core.constants import JobStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.logging import get_logger
from app.models.job import Job
from app.repositories.job import JobRepository
from app.repositories.project import ProjectRepository
from app.schemas.job import JobCreate, JobStatusUpdate

logger = get_logger(__name__)

# Valid state transitions: source_status -> set of allowed target_statuses
VALID_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.QUEUED: {JobStatus.PROCESSING, JobStatus.FAILED},
    JobStatus.PROCESSING: {JobStatus.COMPLETED, JobStatus.FAILED},
    JobStatus.COMPLETED: set(),
    JobStatus.FAILED: set(),
}


class JobService:
    """Service orchestrating business operations and lifecycle transitions for Jobs."""

    def __init__(self, repository: JobRepository, project_repository: ProjectRepository) -> None:
        self.repository = repository
        self.project_repository = project_repository

    async def create_job(self, data: JobCreate) -> Job:
        """Create a new job for an existing project with initial status QUEUED."""
        project = await self.project_repository.get_by_id(data.project_id)
        if not project:
            logger.info("project_not_found_for_job", project_id=str(data.project_id))
            raise NotFoundError(f"Project with ID '{data.project_id}' not found")

        job = Job(
            project_id=data.project_id,
            job_type=data.job_type,
            status=JobStatus.QUEUED,
            payload=data.payload,
            error_message=None,
        )
        created = await self.repository.create(job)
        logger.info("job_created", job_id=str(created.id), project_id=str(data.project_id), job_type=created.job_type)
        return created

    async def get_job(self, job_id: uuid.UUID) -> Job:
        """Retrieve a job by ID or raise NotFoundError."""
        job = await self.repository.get_by_id(job_id)
        if not job:
            logger.info("job_not_found", job_id=str(job_id))
            raise NotFoundError(f"Job with ID '{job_id}' not found")
        return job

    async def list_jobs(self, project_id: uuid.UUID) -> Sequence[Job]:
        """List all jobs for an existing project."""
        project = await self.project_repository.get_by_id(project_id)
        if not project:
            logger.info("project_not_found_for_job_list", project_id=str(project_id))
            raise NotFoundError(f"Project with ID '{project_id}' not found")

        return await self.repository.list_by_project(project_id)

    async def update_status(self, job_id: uuid.UUID, data: JobStatusUpdate) -> Job:
        """Validate and execute a lifecycle state transition."""
        job = await self.get_job(job_id)

        target_status = data.status
        allowed_targets = VALID_TRANSITIONS.get(job.status, set())

        if target_status not in allowed_targets:
            logger.warning(
                "invalid_job_status_transition",
                job_id=str(job_id),
                current_status=job.status,
                target_status=target_status,
            )
            raise BadRequestError(
                f"Invalid status transition from '{job.status}' to '{target_status}'"
            )

        job.status = target_status

        if target_status == JobStatus.FAILED:
            job.error_message = data.error_message or "Job execution failed"
        elif target_status == JobStatus.COMPLETED:
            job.error_message = None

        updated = await self.repository.update(job)
        logger.info(
            "job_status_updated",
            job_id=str(job_id),
            new_status=job.status,
            error_message=job.error_message,
        )
        return updated
    async def claim_job(self, job_id: uuid.UUID) -> Job | None:
        """
        Attempt to atomically claim a job for processing (QUEUED -> PROCESSING).
        Returns the Job if successfully claimed, or None if not in QUEUED state.
        """
        claimed = await self.repository.claim_job(job_id)
        if claimed:
            logger.info("job_claimed_for_processing", job_id=str(job_id))
        return claimed
