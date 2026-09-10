"""OutboxEvent database model for transactional outbox pattern."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import OutboxStatus
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OutboxEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Generic outbox event representing a message to be published asynchronously."""

    __tablename__ = "outbox_events"

    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[OutboxStatus] = mapped_column(
        SQLEnum(OutboxStatus, native_enum=False, length=50),
        default=OutboxStatus.PENDING,
        nullable=False,
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_outbox_events_status_available_at", "status", "available_at"),
    )

    def __repr__(self) -> str:
        return f"<OutboxEvent {self.id} ({self.event_type}) - {self.status}>"
