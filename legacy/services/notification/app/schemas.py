from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models import NotificationType


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    recipient_employee_id: UUID
    notification_type: NotificationType
    title: str
    message: str
    source_event_id: UUID
    project_id: UUID | None
    task_id: UUID | None
    report_id: UUID | None
    read_at: datetime | None
    created_at: datetime


class NotificationPage(BaseModel):
    items: list[NotificationResponse]
    next_cursor: str | None
    has_next_page: bool


class UnreadCount(BaseModel):
    count: int


class MarkAllResult(BaseModel):
    updated_count: int
