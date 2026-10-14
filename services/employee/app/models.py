import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ApplicationRole(enum.StrEnum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    MEMBER = "MEMBER"


class ProvisioningStatus(enum.StrEnum):
    COMPLETE = "COMPLETE"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    keycloak_subject: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[ApplicationRole] = mapped_column(Enum(ApplicationRole, name="application_role"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    provisioning_status: Mapped[ProvisioningStatus] = mapped_column(
        Enum(ProvisioningStatus, name="provisioning_status"),
        default=ProvisioningStatus.COMPLETE,
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class ProvisioningRequest(Base):
    __tablename__ = "provisioning_requests"

    idempotency_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id"), unique=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
