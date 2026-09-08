"""Job endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_job_service,
    require_job_view,
    require_management,
)
from app.core.security import AuthenticatedUser
from app.schemas.job import JobCreate, JobResponse, JobStatusUpdate
from app.services.job import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: JobCreate,
    identity: AuthenticatedUser = Depends(require_management),
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    """Create a new background job. Requires ADMIN or MANAGER role."""
    job = await service.create_job(data=payload)
    return JobResponse.model_validate(job)


@router.get("", response_model=list[JobResponse], status_code=status.HTTP_200_OK)
async def list_jobs(
    project_id: uuid.UUID = Query(..., description="Filter jobs by project UUID"),
    identity: AuthenticatedUser = Depends(require_job_view),
    service: JobService = Depends(get_job_service),
) -> list[JobResponse]:
    """List all jobs for a project. Requires ADMIN, MANAGER, or MEMBER role."""
    jobs = await service.list_jobs(project_id=project_id)
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
