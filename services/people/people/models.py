"""The people service exclusively owns account and employment association data."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
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
