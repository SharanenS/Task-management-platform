"""Repository for Project database operations."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project


class ProjectRepository:
    """Repository handling persistence operations for Project entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, project: Project) -> Project:
        """Add a new project to the database session and flush/refresh."""
        self.session.add(project)
        await self.session.flush()
        await self.session.refresh(project)
        return project

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        """Fetch a single project by its primary key UUID."""
        stmt = select(Project).where(Project.id == project_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> Sequence[Project]:
        """Fetch all projects ordered by creation time descending."""
        stmt = select(Project).order_by(Project.created_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, project: Project) -> Project:
        """Flush changes to an existing project entity and refresh."""
        self.session.add(project)
        await self.session.flush()
        await self.session.refresh(project)
        return project

    async def delete(self, project: Project) -> None:
        """Delete a project entity from the session."""
        await self.session.delete(project)
        await self.session.flush()
