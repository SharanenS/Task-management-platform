"""Repository for OutboxEvent database operations."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import OutboxStatus
from app.models.outbox import OutboxEvent


class OutboxRepository:
    """Repository handling persistence and concurrency-safe polling for OutboxEvent entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, event: OutboxEvent) -> OutboxEvent:
        """Add a new outbox event to the current database session."""
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def get_by_id(self, event_id: uuid.UUID) -> OutboxEvent | None:
        """Fetch an outbox event by its primary key UUID."""
        stmt = select(OutboxEvent).where(OutboxEvent.id == event_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pending_events(self, limit: int = 50) -> Sequence[OutboxEvent]:
        """
        Fetch pending events eligible for publication.
        Uses FOR UPDATE SKIP LOCKED to guarantee safe concurrent publisher polling across instances.
        """
        stmt = (
            select(OutboxEvent)
            .where(
                OutboxEvent.status == OutboxStatus.PENDING,
                OutboxEvent.available_at <= func.now(),
            )
            .order_by(OutboxEvent.available_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def mark_published(self, event_id: uuid.UUID) -> OutboxEvent | None:
        """Mark an outbox event as successfully published and clear error details."""
        stmt = (
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(
                status=OutboxStatus.PUBLISHED,
                published_at=func.now(),
                last_error=None,
                updated_at=func.now(),
            )
            .returning(OutboxEvent)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def record_failure(self, event_id: uuid.UUID, error_message: str) -> OutboxEvent | None:
        """Record publication failure, increment attempt count, and retain event as PENDING."""
        stmt = (
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(
                attempt_count=OutboxEvent.attempt_count + 1,
                last_error=error_message,
                updated_at=func.now(),
            )
            .returning(OutboxEvent)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
