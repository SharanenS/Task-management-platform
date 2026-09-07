"""User repository — persistence layer for User model."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).options(selectinload(User.roles)).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).options(selectinload(User.roles)).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, skip: int = 0, limit: int = 100) -> tuple[list[User], int]:
        count_stmt = select(User)
        count_result = await self.session.execute(count_stmt)
        total = len(count_result.scalars().all())

        stmt = (
            select(User)
            .options(selectinload(User.roles))
            .offset(skip)
            .limit(limit)
            .order_by(User.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def update(self, user: User) -> User:
        await self.session.flush()
        return user