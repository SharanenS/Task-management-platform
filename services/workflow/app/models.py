import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TriggerType(enum.StrEnum):
    TASK_COMPLETED = "TASK_COMPLETED"


class ActionType(enum.StrEnum):
    PROJECT_TASK_EXPORT = "PROJECT_TASK_EXPORT"


class ExecutionStatus(enum.StrEnum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class InboxStatus(enum.StrEnum):
    RECEIVED = "RECEIVED"
    PROCESSED = "PROCESSED"
    QUARANTINED = "QUARANTINED"


class WorkflowRule(Base):
    __tablename__ = "workflow_rules"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(200))
    trigger_type: Mapped[TriggerType] = mapped_column(
        Enum(TriggerType, name="workflow_trigger_type")
    )
    action_type: Mapped[ActionType] = mapped_column(Enum(ActionType, name="workflow_action_type"))
    enabled: Mapped[bool] = mapped_column(default=True, index=True)
    creator_employee_id: Mapped[uuid.UUID] = mapped_column(index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class SourceEvent(Base):
    __tablename__ = "workflow_source_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    schema_version: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(64))
    project_id: Mapped[uuid.UUID] = mapped_column(index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(index=True)
    status: Mapped[InboxStatus] = mapped_column(
        Enum(InboxStatus, name="workflow_inbox_status"), default=InboxStatus.RECEIVED
    )
    failure_classification: Mapped[str | None] = mapped_column(String(64), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    __table_args__ = (UniqueConstraint("rule_id", "source_event_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_rules.id", ondelete="CASCADE"), index=True
    )
    source_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_source_events.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(index=True)
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus, name="workflow_execution_status"),
        default=ExecutionStatus.PENDING,
        index=True,
    )
    resulting_job_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    failure_classification: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rule: Mapped[WorkflowRule] = relationship()
