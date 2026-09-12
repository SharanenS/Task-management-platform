"""Job endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db,
    get_job_service,
    require_job_view,
    require_management,
)
from app.core.constants import JobStatus
from app.core.logging import get_logger
from app.core.security import AuthenticatedUser
from app.schemas.job import JobCreate, JobResponse, JobStatsResponse, JobStatusUpdate
from app.services.job import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = get_logger(__name__)


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: JobCreate,
    identity: AuthenticatedUser = Depends(require_management),
    service: JobService = Depends(get_job_service),
    session: AsyncSession = Depends(get_db),
) -> JobResponse:
    """
    Create a new background job with an atomic outbox event.
    The Job and OutboxEvent are durably persisted in a single PostgreSQL commit.
    Requires ADMIN or MANAGER role.
    """
    job = await service.create_job(data=payload)
    # Commit the single transaction holding both Job and OutboxEvent
    await session.commit()
    return JobResponse.model_validate(job)


@router.get("/stats", response_model=JobStatsResponse, status_code=status.HTTP_200_OK)
async def get_job_stats(
    project_id: uuid.UUID | None = Query(default=None, description="Filter stats by project UUID"),
    identity: AuthenticatedUser = Depends(require_job_view),
    service: JobService = Depends(get_job_service),
) -> JobStatsResponse:
    """Retrieve aggregate job counts by status. Requires ADMIN, MANAGER, or MEMBER role."""
    stats = await service.get_job_stats(project_id=project_id)
    return JobStatsResponse.model_validate(stats)


@router.get("", response_model=list[JobResponse], status_code=status.HTTP_200_OK)
async def list_jobs(
    project_id: uuid.UUID | None = Query(default=None, description="Filter jobs by project UUID"),
    status: JobStatus | None = Query(default=None, description="Filter jobs by lifecycle status"),
    job_type: str | None = Query(default=None, description="Filter jobs by job type"),
    skip: int = Query(default=0, ge=0, description="Pagination offset"),
    limit: int = Query(default=50, gt=0, le=100, description="Pagination limit"),
    identity: AuthenticatedUser = Depends(require_job_view),
    service: JobService = Depends(get_job_service),
) -> list[JobResponse]:
    """List background jobs with optional project, status, and job_type filtering and pagination. Requires ADMIN, MANAGER, or MEMBER role."""
    jobs = await service.list_jobs(
        project_id=project_id,
        status=status,
        job_type=job_type,
        skip=skip,
        limit=limit,
    )
    return [JobResponse.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=JobResponse, status_code=status.HTTP_200_OK)
async def get_job(
    job_id: uuid.UUID,
    identity: AuthenticatedUser = Depends(require_job_view),
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    """Retrieve a job by ID. Requires ADMIN, MANAGER, or MEMBER role."""
    job = await service.get_job(job_id=job_id)
    return JobResponse.model_validate(job)


@router.patch("/{job_id}/status", response_model=JobResponse, status_code=status.HTTP_200_OK)
async def update_job_status(
    job_id: uuid.UUID,
    payload: JobStatusUpdate,
    identity: AuthenticatedUser = Depends(require_management),
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    """Update job lifecycle status. Requires ADMIN or MANAGER role."""
    job = await service.update_status(job_id=job_id, data=payload)
    return JobResponse.model_validate(job)
