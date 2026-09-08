"""Project domain model."""

from typing import TYPE_CHECKING

from sqlalchemy import Enum as SQLEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ProjectStatus
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.job import Job


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Project domain entity."""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        SQLEnum(ProjectStatus, native_enum=False, length=50),
        default=ProjectStatus.PLANNING,
        nullable=False,
    )
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    jobs: Mapped[list["Job"]] = relationship(
        "Job",
        back_populates="project",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Project {self.name} ({self.id}) - {self.status}>"
