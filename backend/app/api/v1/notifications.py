"""Notification endpoints."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db
from app.schemas.notification import NotificationResponse
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    current_user: CurrentUser,
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """List notifications for the current user."""
    service = NotificationService(db)
    return await service.list_notifications(current_user.id, unread_only)


@router.patch("/{notification_id}/read", status_code=204)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Mark a notification as read."""
    service = NotificationService(db)
    await service.mark_as_read(notification_id, current_user.id)