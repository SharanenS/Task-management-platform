"""Repository for Job database operations."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select, text, update
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

    async def claim_job(
        self,
        job_id: uuid.UUID,
        claim_owner: str | None = None,
        lease_seconds: int | None = None,
    ) -> Job | None:
        """
        Atomically transition a job from QUEUED to PROCESSING.
        Stamps processing_started_at, execution_lease_until, and execution_claim_owner.
        Returns the updated Job if the claim succeeded, or None if the job was not in QUEUED state.
        """
        owner = claim_owner or f"worker-{uuid.uuid4().hex[:8]}"
        l_sec = int(lease_seconds) if lease_seconds is not None else 300
        stmt = (
            update(Job)
            .where(Job.id == job_id, Job.status == JobStatus.QUEUED)
            .values(
                status=JobStatus.PROCESSING,
                processing_started_at=func.now(),
                execution_lease_until=func.now() + text(f"INTERVAL '{l_sec} SECONDS'"),
                execution_claim_owner=owner,
                error_message=None,
                updated_at=func.now(),
            )
            .returning(Job)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def reclaim_expired_jobs(
        self,
        limit: int = 50,
        claim_owner: str | None = None,
        lease_seconds: int = 300,
    ) -> Sequence[Job]:
        """
        Atomically reclaim a batch of expired PROCESSING jobs using FOR UPDATE SKIP LOCKED.
        Eligible jobs have status == PROCESSING, execution_lease_until IS NOT NULL, and execution_lease_until < now().
        Replaces execution_claim_owner, extends execution_lease_until, and refreshes processing_started_at.
        """
        owner = claim_owner or f"recovery-{uuid.uuid4().hex[:8]}"
        l_sec = int(lease_seconds)
        stmt = (
            select(Job)
            .where(
                Job.status == JobStatus.PROCESSING,
                Job.execution_lease_until.is_not(None),
                Job.execution_lease_until < func.now(),
            )
            .order_by(Job.execution_lease_until.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(stmt)
        jobs = result.scalars().all()
        if not jobs:
            return []

        job_ids = [j.id for j in jobs]
        update_stmt = (
            update(Job)
            .where(Job.id.in_(job_ids))
            .values(
                status=JobStatus.PROCESSING,
                processing_started_at=func.now(),
                execution_lease_until=func.now() + text(f"INTERVAL '{l_sec} SECONDS'"),
                execution_claim_owner=owner,
                updated_at=func.now(),
            )
            .returning(Job)
        )
        updated_result = await self.session.execute(update_stmt)
        return updated_result.scalars().all()

    async def complete_job(
        self,
        job_id: uuid.UUID,
        claim_owner: str,
    ) -> Job | None:
        """
        Mark a job as COMPLETED and clear execution ownership fields.
        Only transitions if status == PROCESSING, execution_claim_owner matches, and lease is still active.
        Returns the updated Job if successful, or None if ownership was lost or lease expired.
        """
        stmt = (
            update(Job)
            .where(
                Job.id == job_id,
                Job.status == JobStatus.PROCESSING,
                Job.execution_claim_owner == claim_owner,
                Job.execution_lease_until >= func.now(),
            )
            .values(
                status=JobStatus.COMPLETED,
                processing_started_at=None,
                execution_lease_until=None,
                execution_claim_owner=None,
                error_message=None,
                updated_at=func.now(),
            )
            .returning(Job)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def fail_job(
        self,
        job_id: uuid.UUID,
        claim_owner: str,
        error_message: str,
    ) -> Job | None:
        """
        Mark a job as FAILED, persist error message, and clear execution ownership fields.
        Only transitions if status == PROCESSING, execution_claim_owner matches, and lease is still active.
        Returns the updated Job if successful, or None if ownership was lost or lease expired.
        """
        stmt = (
            update(Job)
            .where(
                Job.id == job_id,
                Job.status == JobStatus.PROCESSING,
                Job.execution_claim_owner == claim_owner,
                Job.execution_lease_until >= func.now(),
            )
            .values(
                status=JobStatus.FAILED,
                processing_started_at=None,
                execution_lease_until=None,
                execution_claim_owner=None,
                error_message=error_message,
                updated_at=func.now(),
            )
            .returning(Job)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
