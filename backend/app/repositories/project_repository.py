"""Project repository — persistence layer for Project model."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import Project


class ProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        stmt = (
            select(Project)
            .options(selectinload(Project.creator))
            .where(Project.id == project_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, skip: int = 0, limit: int = 100) -> tuple[list[Project], int]:
        count_stmt = select(func.count()).select_from(Project)
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()

        stmt = (
            select(Project)
            .options(selectinload(Project.creator))
            .offset(skip)
            .limit(limit)
            .order_by(Project.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def create(self, project: Project) -> Project:
        self.session.add(project)
        await self.session.flush()
        return project

    async def update(self, project: Project) -> Project:
        await self.session.flush()
        return project

    async def delete(self, project: Project) -> None:
        await self.session.delete(project)
        await self.session.flush()