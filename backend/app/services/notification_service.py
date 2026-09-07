"""Notification service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.notification_repository import NotificationRepository
from app.schemas.notification import NotificationResponse


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.notif_repo = NotificationRepository(session)

    async def list_notifications(
        self, user_id: uuid.UUID, unread_only: bool = False
    ) -> list[NotificationResponse]:
        notifs = await self.notif_repo.list_by_user(user_id, unread_only)
        return [
            NotificationResponse(
                id=n.id,
                type=n.type,
                title=n.title,
                message=n.message,
                is_read=n.is_read,
                metadata_=n.metadata_,
                created_at=n.created_at,
            )
            for n in notifs
        ]

    async def mark_as_read(self, notification_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self.notif_repo.mark_as_read(notification_id, user_id)