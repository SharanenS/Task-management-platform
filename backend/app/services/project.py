"""Service layer for Project business logic."""

import uuid
from collections.abc import Sequence

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.project import Project
from app.repositories.project import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate

logger = get_logger(__name__)


class ProjectService:
    """Service orchestrating business operations for Project entities."""

    def __init__(self, repository: ProjectRepository) -> None:
        self.repository = repository

    async def create_project(self, data: ProjectCreate, owner_id: str) -> Project:
        """Create a new project with the authenticated owner."""
        project = Project(
            name=data.name,
            description=data.description.strip() if data.description else None,
            status=data.status,
            owner_id=owner_id,
        )
        created = await self.repository.create(project)
        logger.info("project_created", project_id=str(created.id), owner_id=owner_id, name=created.name)
        return created

    async def get_project(self, project_id: uuid.UUID) -> Project:
        """Retrieve a project by ID or raise NotFoundError."""
        project = await self.repository.get_by_id(project_id)
        if not project:
            logger.info("project_not_found", project_id=str(project_id))
            raise NotFoundError(f"Project with ID '{project_id}' not found")
        return project

    async def list_projects(self) -> Sequence[Project]:
        """List all projects."""
        return await self.repository.list_all()

    async def update_project(self, project_id: uuid.UUID, data: ProjectUpdate) -> Project:
        """Update an existing project's fields."""
        project = await self.get_project(project_id)

        update_data = data.model_dump(exclude_unset=True)
        if "name" in update_data and update_data["name"] is not None:
            project.name = update_data["name"]
        if "description" in update_data:
            project.description = update_data["description"].strip() if update_data["description"] else None
        if "status" in update_data and update_data["status"] is not None:
            project.status = update_data["status"]

        updated = await self.repository.update(project)
        logger.info("project_updated", project_id=str(project_id))
        return updated

    async def delete_project(self, project_id: uuid.UUID) -> None:
        """Delete an existing project."""
        project = await self.get_project(project_id)
        await self.repository.delete(project)
        logger.info("project_deleted", project_id=str(project_id))
