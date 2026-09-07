"""Notification-related Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    message: str | None
    is_read: bool
    metadata_: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}