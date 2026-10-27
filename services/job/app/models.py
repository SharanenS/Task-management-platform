import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class JobType(enum.StrEnum):
    PROJECT_TASK_EXPORT = "PROJECT_TASK_EXPORT"


class JobStatus(enum.StrEnum):
    SUBMITTED = "SUBMITTED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AttemptStatus(enum.StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    ABANDONED = "ABANDONED"


class PublicationStatus(enum.StrEnum):
    PENDING = "PENDING"
    IN_FLIGHT = "IN_FLIGHT"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("submitter_employee_id", "idempotency_key", name="uq_job_actor_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_type: Mapped[JobType] = mapped_column(Enum(JobType, name="job_type"))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus, name="job_status"))
    submitter_employee_id: Mapped[uuid.UUID] = mapped_column(index=True)
    related_project_id: Mapped[uuid.UUID | None] = mapped_column(index=True, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    result_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    result_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    result_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_truncated: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    failure_classification: Mapped[str | None] = mapped_column(String(100), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_generation: Mapped[int] = mapped_column(Integer, default=0)
    retry_exhausted: Mapped[bool] = mapped_column(Boolean, default=False)
    manual_retry_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    attempts: Mapped[list["JobAttempt"]] = relationship(
        cascade="all, delete-orphan", back_populates="job"
    )
    publications: Mapped[list["OutboxEvent"]] = relationship(
        cascade="all, delete-orphan", back_populates="job"
    )

    @property
    def publication(self) -> "OutboxEvent | None":
        return max(self.publications, key=lambda item: item.execution_generation, default=None)


class OutboxEvent(Base):
    __tablename__ = "job_publication_outbox"
    __table_args__ = (
        UniqueConstraint(
            "job_id", "execution_generation", "event_type", name="uq_job_publication_generation"
        ),
        Index(
            "ix_job_publication_claim",
            "status",
            "available_at",
            "lease_expires_at",
            "created_at",
            "id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(50), default="EXECUTE_JOB")
    execution_generation: Mapped[int] = mapped_column(Integer, default=1)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[PublicationStatus] = mapped_column(
        Enum(PublicationStatus, name="publication_status")
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_classification: Mapped[str | None] = mapped_column(String(50), nullable=True)
    job: Mapped[Job] = relationship(back_populates="publications")


class JobAttempt(Base):
    __tablename__ = "job_attempts"
    __table_args__ = (UniqueConstraint("job_id", "attempt_number", name="uq_job_attempt_number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[AttemptStatus] = mapped_column(Enum(AttemptStatus, name="job_attempt_status"))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    safe_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    execution_generation: Mapped[int] = mapped_column(Integer, default=1)
    execution_fence: Mapped[int] = mapped_column(Integer, default=1)
    execution_lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_acquired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    abandoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    job: Mapped[Job] = relationship(back_populates="attempts")
