"""Repository for Job database operations."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import JobStatus
from app.models.job import Job


class JobRepository:
    """Repository handling persistence operations for Job entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, job: Job) -> Job:
        """Add a new job to the database session and flush/refresh."""
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def get_by_id(self, job_id: uuid.UUID) -> Job | None:
        """Fetch a single job by its primary key UUID."""
        stmt = select(Job).where(Job.id == job_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: uuid.UUID) -> Sequence[Job]:
        """Fetch all jobs for a project ordered by creation time descending."""
        stmt = select(Job).where(Job.project_id == project_id).order_by(Job.created_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_jobs(
        self,
        project_id: uuid.UUID | None = None,
        status: JobStatus | None = None,
        job_type: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[Job]:
        """Fetch jobs with optional filtering by project, status, and job type with pagination."""
        stmt = select(Job)
        if project_id is not None:
            stmt = stmt.where(Job.project_id == project_id)
        if status is not None:
            stmt = stmt.where(Job.status == status)
        if job_type is not None:
            stmt = stmt.where(Job.job_type == job_type)
        stmt = stmt.order_by(Job.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_job_stats(self, project_id: uuid.UUID | None = None) -> dict[str, int]:
        """Compute aggregated job counts by status."""
        stmt = select(Job.status, func.count(Job.id)).group_by(Job.status)
        if project_id is not None:
            stmt = stmt.where(Job.project_id == project_id)
        result = await self.session.execute(stmt)
        counts: dict[JobStatus, int] = {s: 0 for s in JobStatus}
        for status_val, count in result.all():
            counts[status_val] = count
        total = sum(counts.values())
        return {
            "total_count": total,
            "queued_count": counts.get(JobStatus.QUEUED, 0),
            "processing_count": counts.get(JobStatus.PROCESSING, 0),
            "completed_count": counts.get(JobStatus.COMPLETED, 0),
            "failed_count": counts.get(JobStatus.FAILED, 0),
        }

    async def update(self, job: Job) -> Job:
        """Flush changes to an existing job entity and refresh."""
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def claim_job(self, job_id: uuid.UUID) -> Job | None:
        """
        Atomically transition a job from QUEUED to PROCESSING.
        Returns the updated Job if the claim succeeded, or None if the job was not in QUEUED state.
        """
        stmt = (
            update(Job)
            .where(Job.id == job_id, Job.status == JobStatus.QUEUED)
            .values(status=JobStatus.PROCESSING, updated_at=func.now())
            .returning(Job)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
