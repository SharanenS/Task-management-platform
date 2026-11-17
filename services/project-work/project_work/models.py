"""Project-work owns calendars; account identifiers are references, not copied accounts."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .calendar import TZDB_VERSION


class Base(DeclarativeBase):
    pass


class CalendarPreview(Base):
    __tablename__ = "calendar_previews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    issuer: Mapped[str] = mapped_column(String(512))
    actor_id: Mapped[str] = mapped_column(String(36))
    base_version_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "calendar_versions.id",
            name="fk_calendar_preview_base",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        nullable=True,
    )
    config: Mapped[str] = mapped_column(Text)
    config_hash: Mapped[str] = mapped_column(String(64))
    tzdb_version: Mapped[str] = mapped_column(String(30), default=TZDB_VERSION)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CalendarVersion(Base):
    __tablename__ = "calendar_versions"
    __table_args__ = (UniqueConstraint("issuer", "number", name="uq_calendar_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    issuer: Mapped[str] = mapped_column(String(512))
    number: Mapped[int] = mapped_column(Integer)
    preview_id: Mapped[str] = mapped_column(
        ForeignKey("calendar_previews.id", ondelete="RESTRICT"), unique=True
    )
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    actor_id: Mapped[str] = mapped_column(String(36))
    config: Mapped[str] = mapped_column(Text)
    config_hash: Mapped[str] = mapped_column(String(64))
    tzdb_version: Mapped[str] = mapped_column(String(30), default=TZDB_VERSION)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
