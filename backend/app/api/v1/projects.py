"""Project CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user import UserResponse
from app.api.deps import CurrentUser, get_db, require_permission
from app.core.constants import Permission
from app.schemas.project import ProjectCreate, ProjectListResponse, ProjectResponse, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    request: Request,
    body: ProjectCreate,
    current_user: UserResponse = Depends(require_permission(Permission.PROJECTS_CREATE)),
    db: AsyncSession = Depends(get_db),
):
    """Create a new project."""
    service = ProjectService(db)
    return await service.create_project(
        body,
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
    )


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    skip: int = 0,
    limit: int = 100,
    current_user: UserResponse = Depends(require_permission(Permission.PROJECTS_READ)),
    db: AsyncSession = Depends(get_db),
):
    """List all projects."""
    service = ProjectService(db)
    projects, total = await service.list_projects(skip, limit)
    return ProjectListResponse(projects=projects, total=total)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    current_user: UserResponse = Depends(require_permission(Permission.PROJECTS_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Get a project by ID."""
    service = ProjectService(db)
    return await service.get_project(project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    request: Request,
    current_user: UserResponse = Depends(require_permission(Permission.PROJECTS_UPDATE)),
    db: AsyncSession = Depends(get_db),
):
    """Update a project (owner or admin)."""
    service = ProjectService(db)
    return await service.update_project(
        project_id, body,
        user_id=current_user.id,
        user_permissions=current_user.permissions,
        ip_address=request.client.host if request.client else None,
    )


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    request: Request,
    current_user: UserResponse = Depends(require_permission(Permission.PROJECTS_DELETE)),
    db: AsyncSession = Depends(get_db),
):
    """Delete a project (owner or admin)."""
    service = ProjectService(db)
    await service.delete_project(
        project_id,
        user_id=current_user.id,
        user_permissions=current_user.permissions,
        ip_address=request.client.host if request.client else None,
    )