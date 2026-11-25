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


class DeliveryState(Base):
    __tablename__ = "project_delivery_state"
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), primary_key=True
    )
    schedule_version: Mapped[int] = mapped_column(Integer)


class DeliveryAssessment(Base):
    __tablename__ = "project_delivery_assessments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ASSESSED', 'UNASSESSED')", name="ck_delivery_assessment_status"
        ),
        CheckConstraint(
            "(status = 'ASSESSED' AND forecast_at IS NOT NULL) OR "
            "(status = 'UNASSESSED' AND forecast_at IS NULL)",
            name="ck_delivery_forecast_presence",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    schedule_version: Mapped[int] = mapped_column(Integer)
    project_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    forecast_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OwnerEscalation(Base):
    __tablename__ = "project_owner_escalations"
    __table_args__ = (
        CheckConstraint("status IN ('PENDING', 'DECIDED')", name="ck_owner_escalation_status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    source_request_id: Mapped[str] = mapped_column(String(36), unique=True)
    assessment_id: Mapped[str | None] = mapped_column(
        ForeignKey("project_delivery_assessments.id", ondelete="RESTRICT")
    )
    reason: Mapped[str] = mapped_column(Text)
    affected_team: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class OwnerDecisionPreview(Base):
    __tablename__ = "project_owner_decision_previews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    escalation_id: Mapped[str] = mapped_column(
        ForeignKey("project_owner_escalations.id", ondelete="RESTRICT")
    )
    actor_id: Mapped[str] = mapped_column(String(36))
    project_version: Mapped[int] = mapped_column(Integer)
    escalation_version: Mapped[int] = mapped_column(Integer)
    assessment_id: Mapped[str] = mapped_column(
        ForeignKey("project_delivery_assessments.id", ondelete="RESTRICT")
    )
    calendar_version_id: Mapped[str] = mapped_column(
        ForeignKey("calendar_versions.id", ondelete="RESTRICT")
    )
    deadline_date: Mapped[str] = mapped_column(String(10))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_local: Mapped[str] = mapped_column(String(50))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OwnerDecision(Base):
    __tablename__ = "project_owner_decisions"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('REVISE_DEADLINE', 'ACCEPT_FORECAST_LATE', 'REQUEST_REPLAN')",
            name="ck_owner_decision_outcome",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    escalation_id: Mapped[str] = mapped_column(
        ForeignKey("project_owner_escalations.id", ondelete="RESTRICT"), unique=True
    )
    assessment_id: Mapped[str | None] = mapped_column(
        ForeignKey("project_delivery_assessments.id", ondelete="RESTRICT")
    )
    preview_id: Mapped[str | None] = mapped_column(
        ForeignKey("project_owner_decision_previews.id", ondelete="RESTRICT"), unique=True
    )
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(36))
    actor_name: Mapped[str] = mapped_column(String(150))
    actor_role: Mapped[str] = mapped_column(String(20))
    outcome: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    affected_team: Mapped[str] = mapped_column(String(300))
    forecast_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assessment_state: Mapped[str] = mapped_column(String(20))
    previous_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revised_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    previous_overdue: Mapped[bool] = mapped_column(Boolean)
    project_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ReviewFallback(Base):
    __tablename__ = "project_review_fallbacks"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('REVIEWS', 'EXTENSIONS', 'BOTH')", name="ck_review_fallback_scope"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(36))
    actor_name: Mapped[str] = mapped_column(String(150))
    leader_id: Mapped[str | None] = mapped_column(String(36))
    leader_name: Mapped[str | None] = mapped_column(String(150))
    scope: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[str | None] = mapped_column(String(36))
    revocation_reason: Mapped[str | None] = mapped_column(Text)
    revocation_request_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    revocation_hash: Mapped[str | None] = mapped_column(String(64))


class WorkTask(Base):
    __tablename__ = "work_tasks"
    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_task_version"),
        CheckConstraint(
            "status IN ('PENDING','IN_PROGRESS','AWAITING_REVIEW','COMPLETED','CANCELLED')",
            name="ck_task_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[str] = mapped_column(Text)
    acceptance_criteria: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="PENDING")
    version: Mapped[int] = mapped_column(Integer, default=1)
    creator_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class TaskAssignment(Base):
    __tablename__ = "task_assignments"
    __table_args__ = (
        Index(
            "uq_task_active_assignment",
            "task_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
            sqlite_where=text("ended_at IS NULL"),
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(
        ForeignKey("work_tasks.id", ondelete="RESTRICT"), index=True
    )
    account_id: Mapped[str] = mapped_column(String(36))
    display_name: Mapped[str] = mapped_column(String(150))
    actor_id: Mapped[str] = mapped_column(String(36))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskChange(Base):
    __tablename__ = "task_changes"
    __table_args__ = (UniqueConstraint("task_id", "task_version", name="uq_task_change_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(
        ForeignKey("work_tasks.id", ondelete="RESTRICT"), index=True
    )
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(36))
    actor_name: Mapped[str] = mapped_column(String(150))
    action: Mapped[str] = mapped_column(String(12))
    reason: Mapped[str] = mapped_column(Text)
    before: Mapped[str] = mapped_column(Text)
    after: Mapped[str] = mapped_column(Text)
    task_version: Mapped[int] = mapped_column(Integer)
    project_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
