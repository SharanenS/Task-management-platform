"""Project-work owns calendars; account identifiers are references, not copied accounts."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
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


class ProjectPreview(Base):
    __tablename__ = "project_previews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    issuer: Mapped[str] = mapped_column(String(512))
    actor_id: Mapped[str] = mapped_column(String(36))
    actor_name: Mapped[str] = mapped_column(String(150))
    name: Mapped[str] = mapped_column(String(150))
    objectives: Mapped[str] = mapped_column(Text)
    deadline_date: Mapped[str] = mapped_column(String(10))
    approved_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_local: Mapped[str] = mapped_column(String(50))
    calendar_version_id: Mapped[str] = mapped_column(
        ForeignKey("calendar_versions.id", ondelete="RESTRICT")
    )
    calendar_number: Mapped[int] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(String(100))
    tzdb_version: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    issuer: Mapped[str] = mapped_column(String(512))
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    preview_id: Mapped[str] = mapped_column(
        ForeignKey("project_previews.id", ondelete="RESTRICT"), unique=True
    )
    name: Mapped[str] = mapped_column(String(150))
    objectives: Mapped[str] = mapped_column(Text)
    creator_id: Mapped[str] = mapped_column(String(36))
    creator_name: Mapped[str] = mapped_column(String(150))
    owner_id: Mapped[str] = mapped_column(String(36))
    owner_name: Mapped[str] = mapped_column(String(150))
    deadline_date: Mapped[str] = mapped_column(String(10))
    approved_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_local: Mapped[str] = mapped_column(String(50))
    calendar_version_id: Mapped[str] = mapped_column(
        ForeignKey("calendar_versions.id", ondelete="RESTRICT")
    )
    calendar_number: Mapped[int] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(String(100))
    tzdb_version: Mapped[str] = mapped_column(String(30))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "account_id", name="uq_project_member_account"),
        CheckConstraint(
            "responsibility IN ('CONTRIBUTOR', 'LEADER')", name="ck_project_responsibility"
        ),
        Index(
            "uq_project_active_leader",
            "project_id",
            unique=True,
            postgresql_where=text("active AND responsibility = 'LEADER'"),
            sqlite_where=text("active AND responsibility = 'LEADER'"),
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    issuer: Mapped[str] = mapped_column(String(512))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    account_id: Mapped[str] = mapped_column(String(36))
    display_name: Mapped[str] = mapped_column(String(150))
    responsibility: Mapped[str] = mapped_column(String(20))
    duties: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ProjectMembershipChange(Base):
    __tablename__ = "project_membership_changes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    issuer: Mapped[str] = mapped_column(String(512))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(36))
    target_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(20))
    before: Mapped[str] = mapped_column(Text)
    after: Mapped[str] = mapped_column(Text)
    project_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class CoordinationRecord(Base):
    __tablename__ = "coordination_records"
    __table_args__ = (
        CheckConstraint("kind IN ('UPDATE', 'MEETING', 'CHECK_IN')", name="ck_coordination_kind"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    issuer: Mapped[str] = mapped_column(String(512))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(20))
    topic: Mapped[str] = mapped_column(String(150))
    details: Mapped[str] = mapped_column(Text)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[str] = mapped_column(String(300))
    acknowledgement_required: Mapped[bool] = mapped_column(Boolean)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class CoordinationRecipient(Base):
    __tablename__ = "coordination_recipients"
    __table_args__ = (
        UniqueConstraint("record_id", "account_id", name="uq_coordination_recipient"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    record_id: Mapped[str] = mapped_column(
        ForeignKey("coordination_records.id", ondelete="RESTRICT")
    )
    account_id: Mapped[str] = mapped_column(String(36))
    display_name: Mapped[str] = mapped_column(String(150))


class CoordinationFollowUp(Base):
    __tablename__ = "coordination_follow_ups"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    record_id: Mapped[str] = mapped_column(
        ForeignKey("coordination_records.id", ondelete="RESTRICT")
    )
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(36))
    note: Mapped[str] = mapped_column(Text)
    next_follow_up_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
