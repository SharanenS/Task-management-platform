"""Repository for OutboxEvent database operations."""

import uuid
from collections.abc import Sequence

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import OutboxStatus
from app.models.outbox import OutboxEvent


class OutboxRepository:
    """Repository handling persistence, lease acquisition, and polling for OutboxEvent entities."""

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

    async def claim_events(
        self,
        limit: int = 50,
        lease_seconds: int = 30,
        claim_owner: str | None = None,
    ) -> Sequence[OutboxEvent]:
        """
        Atomically claim a batch of eligible events by transitioning them to CLAIMED with a lease.
        Eligible events are:
        - PENDING events whose available_at <= now()
        - CLAIMED events whose lease has expired (lease_until <= now())
        Uses FOR UPDATE SKIP LOCKED to guarantee safe concurrent publisher claims across instances.
        """
        stmt = (
            select(OutboxEvent)
            .where(
                or_(
                    and_(
                        OutboxEvent.status == OutboxStatus.PENDING,
                        OutboxEvent.available_at <= func.now(),
                    ),
                    and_(
                        OutboxEvent.status == OutboxStatus.CLAIMED,
                        OutboxEvent.lease_until <= func.now(),
                    ),
                )
            )
            .order_by(OutboxEvent.available_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(stmt)
        events = result.scalars().all()
        if not events:
            return []

        event_ids = [e.id for e in events]
        update_stmt = (
            update(OutboxEvent)
            .where(OutboxEvent.id.in_(event_ids))
            .values(
                status=OutboxStatus.CLAIMED,
                claimed_at=func.now(),
                lease_until=func.now() + text(f"INTERVAL '{int(lease_seconds)} SECONDS'"),
                claim_owner=claim_owner,
                updated_at=func.now(),
            )
            .returning(OutboxEvent)
        )
        updated_result = await self.session.execute(update_stmt)
        return updated_result.scalars().all()

    async def mark_published(self, event_id: uuid.UUID, claim_owner: str) -> OutboxEvent | None:
        """
        Mark an outbox event as successfully published and clear lease metadata.
        Only transitions the event if the settling publisher currently owns the active, unexpired claim.
        Returns the updated OutboxEvent if successful, or None if ownership was lost or lease expired.
        """
        stmt = (
            update(OutboxEvent)
            .where(
                OutboxEvent.id == event_id,
                OutboxEvent.status == OutboxStatus.CLAIMED,
                OutboxEvent.claim_owner == claim_owner,
                OutboxEvent.lease_until >= func.now(),
            )
            .values(
                status=OutboxStatus.PUBLISHED,
                published_at=func.now(),
                lease_until=None,
                claim_owner=None,
                last_error=None,
                updated_at=func.now(),
            )
            .returning(OutboxEvent)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def record_failure(
        self,
        event_id: uuid.UUID,
        error_message: str,
        claim_owner: str,
    ) -> OutboxEvent | None:
        """
        Record publication failure, reset to PENDING, increment attempt count, and clear lease.
        Only transitions the event if the settling publisher currently owns the active, unexpired claim.
        Returns the updated OutboxEvent if successful, or None if ownership was lost or lease expired.
        """
        stmt = (
            update(OutboxEvent)
            .where(
                OutboxEvent.id == event_id,
                OutboxEvent.status == OutboxStatus.CLAIMED,
                OutboxEvent.claim_owner == claim_owner,
                OutboxEvent.lease_until >= func.now(),
            )
            .values(
                status=OutboxStatus.PENDING,
                lease_until=None,
                claim_owner=None,
                attempt_count=OutboxEvent.attempt_count + 1,
                last_error=error_message,
                updated_at=func.now(),
            )
            .returning(OutboxEvent)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
