"""Project endpoints."""

import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    get_project_service,
    require_admin,
    require_management,
    require_project_view,
)
from app.core.security import AuthenticatedUser
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.project import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    identity: AuthenticatedUser = Depends(require_management),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """Create a new project. Requires ADMIN or MANAGER role."""
    project = await service.create_project(data=payload, owner_id=identity.sub)
    return ProjectResponse.model_validate(project)


@router.get("", response_model=list[ProjectResponse], status_code=status.HTTP_200_OK)
async def list_projects(
    identity: AuthenticatedUser = Depends(require_project_view),
    service: ProjectService = Depends(get_project_service),
) -> list[ProjectResponse]:
    """List all projects. Requires ADMIN, MANAGER, or MEMBER role."""
    projects = await service.list_projects()
    return [ProjectResponse.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse, status_code=status.HTTP_200_OK)
async def get_project(
    project_id: uuid.UUID,
    identity: AuthenticatedUser = Depends(require_project_view),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """Retrieve a project by ID. Requires ADMIN, MANAGER, or MEMBER role."""
    project = await service.get_project(project_id)
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse, status_code=status.HTTP_200_OK)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    identity: AuthenticatedUser = Depends(require_management),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """Update a project. Requires ADMIN or MANAGER role."""
    project = await service.update_project(project_id=project_id, data=payload)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    identity: AuthenticatedUser = Depends(require_admin),
    service: ProjectService = Depends(get_project_service),
) -> None:
    """Delete a project. Requires ADMIN role."""
    await service.delete_project(project_id=project_id)
