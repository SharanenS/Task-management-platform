"""The people service exclusively owns account and employment association data."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("issuer", "subject", name="uq_account_identity"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    issuer: Mapped[str] = mapped_column(String(512))
    subject: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    profile: Mapped["EmployeeProfile | None"] = relationship(
        back_populates="account", uselist=False
    )
    grants: Mapped[list["CompanyRoleGrant"]] = relationship(back_populates="account")


class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), unique=True
    )
    display_name: Mapped[str] = mapped_column(String(150))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    account: Mapped[Account] = relationship(back_populates="profile")


class CompanyRoleGrant(Base):
    __tablename__ = "company_role_grants"
    __table_args__ = (
        UniqueConstraint("account_id", name="uq_account_company_role"),
        CheckConstraint("role IN ('ADMIN', 'MANAGER', 'EMPLOYEE', 'HR')", name="ck_company_role"),
    )
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(16), primary_key=True)
    account: Mapped[Account] = relationship(back_populates="grants")


class InitialAdminProvisioning(Base):
    __tablename__ = "initial_admin_provisioning"
    __table_args__ = (
        CheckConstraint(
            "state IN ('PENDING_IDENTITY', 'IDENTITY_CREATED', 'COMPLETE')",
            name="ck_admin_provisioning_state",
        ),
    )
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(36), unique=True)
    username: Mapped[str] = mapped_column(String(100))
    email_marker: Mapped[str] = mapped_column(String(254))
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AccountProvisioning(Base):
    __tablename__ = "account_provisioning"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(150))
    role: Mapped[str] = mapped_column(String(16))
    issuer: Mapped[str] = mapped_column(String(512))
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True
    )
    state: Mapped[str] = mapped_column(String(32))
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class AccountAudit(Base):
    __tablename__ = "account_audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    target_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True
    )
    operation_id: Mapped[str | None] = mapped_column(
        ForeignKey("account_provisioning.id", ondelete="RESTRICT"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(32))
    before: Mapped[str] = mapped_column(Text)
    after: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
