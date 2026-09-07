"""Project service — business logic for project CRUD."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.audit_log import AuditLog
from app.models.project import Project
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate

logger = get_logger(__name__)


class ProjectService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.project_repo = ProjectRepository(session)

    async def create_project(
        self, data: ProjectCreate, user_id: uuid.UUID, ip_address: str | None = None
    ) -> ProjectResponse:
        project = Project(
            name=data.name,
            description=data.description,
            created_by=user_id,
        )
        project = await self.project_repo.create(project)

        audit = AuditLog(
            user_id=user_id,
            action=AuditAction.PROJECT_CREATED,
            resource_type="project",
            resource_id=str(project.id),
            metadata_={"name": project.name},
            ip_address=ip_address,
        )
        self.session.add(audit)

        logger.info("project_created", project_id=str(project.id), name=project.name)
        return self._to_response(project)

    async def get_project(self, project_id: uuid.UUID) -> ProjectResponse:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError(f"Project {project_id} not found")
        return self._to_response(project)

    async def list_projects(self, skip: int = 0, limit: int = 100) -> tuple[list[ProjectResponse], int]:
        projects, total = await self.project_repo.list_all(skip, limit)
        return [self._to_response(p) for p in projects], total

    async def update_project(
        self,
        project_id: uuid.UUID,
        data: ProjectUpdate,
        user_id: uuid.UUID,
        user_permissions: list[str],
        ip_address: str | None = None,
    ) -> ProjectResponse:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError(f"Project {project_id} not found")

        # Resource ownership check
        if project.created_by != user_id and "projects.update" not in user_permissions:
            raise ForbiddenError("You can only update your own projects")

        if data.name is not None:
            project.name = data.name
        if data.description is not None:
            project.description = data.description
        if data.status is not None:
            project.status = data.status

        project = await self.project_repo.update(project)

        audit = AuditLog(
            user_id=user_id,
            action=AuditAction.PROJECT_UPDATED,
            resource_type="project",
            resource_id=str(project.id),
            ip_address=ip_address,
        )
        self.session.add(audit)

        return self._to_response(project)

    async def delete_project(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        user_permissions: list[str],
        ip_address: str | None = None,
    ) -> None:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError(f"Project {project_id} not found")

        if project.created_by != user_id and "projects.delete" not in user_permissions:
            raise ForbiddenError("You can only delete your own projects")

        audit = AuditLog(
            user_id=user_id,
            action=AuditAction.PROJECT_DELETED,
            resource_type="project",
            resource_id=str(project.id),
            metadata_={"name": project.name},
            ip_address=ip_address,
        )
        self.session.add(audit)

        await self.project_repo.delete(project)
        logger.info("project_deleted", project_id=str(project_id))

    def _to_response(self, project: Project) -> ProjectResponse:
        return ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            status=project.status,
            created_by=project.created_by,
            creator_name=project.creator.name if project.creator else None,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )