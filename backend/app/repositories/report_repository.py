"""Report repository."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report


class ReportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, report_id: uuid.UUID) -> Report | None:
        stmt = select(Report).where(Report.id == report_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: uuid.UUID, skip: int = 0, limit: int = 50) -> list[Report]:
        stmt = (
            select(Report)
            .where(Report.requested_by == user_id)
            .offset(skip).limit(limit)
            .order_by(Report.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, report: Report) -> Report:
        self.session.add(report)
        await self.session.flush()
        return report

    async def update(self, report: Report) -> Report:
        await self.session.flush()
        return report