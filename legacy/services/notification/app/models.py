import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class NotificationType(enum.StrEnum):
    TASK_ASSIGNED = "TASK_ASSIGNED"
    REPORT_SUCCEEDED = "REPORT_SUCCEEDED"
    REPORT_FAILED = "REPORT_FAILED"


class InboxStatus(enum.StrEnum):
    RECEIVED = "RECEIVED"
    PROCESSED = "PROCESSED"
    QUARANTINED = "QUARANTINED"


class SourceEvent(Base):
    __tablename__ = "notification_source_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[int]
    status: Mapped[InboxStatus] = mapped_column(Enum(InboxStatus, name="notification_inbox_status"))
    failure_classification: Mapped[str | None] = mapped_column(String(64), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("source_event_id", name="uq_notification_source_event"),
        UniqueConstraint(
            "recipient_employee_id", "source_event_id", name="uq_notification_recipient_event"
        ),
        Index("ix_notifications_recipient_created", "recipient_employee_id", "created_at", "id"),
        Index(
            "ix_notifications_recipient_unread", "recipient_employee_id", "read_at", "created_at"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    recipient_employee_id: Mapped[uuid.UUID] = mapped_column(index=True)
    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type")
    )
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(String(500))
    source_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notification_source_events.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    report_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
