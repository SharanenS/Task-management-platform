from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import ProjectRole, ProjectStatus


class ProjectCreateRequest(BaseModel):
    key: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9-]*$")
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.split())


class ProjectUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    expected_version: int = Field(ge=1)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.split())


class ProjectStatusRequest(BaseModel):
    status: ProjectStatus
    expected_version: int = Field(ge=1)


class MembershipCreateRequest(BaseModel):
    employee_id: UUID
    role: ProjectRole


class MembershipRoleRequest(BaseModel):
    role: ProjectRole


class MembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    employee_id: UUID
    role: ProjectRole
    created_at: datetime


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    key: str
    name: str
    description: str | None
    status: ProjectStatus
    creator_employee_id: UUID
    version: int
    created_at: datetime
    updated_at: datetime
    memberships: list[MembershipResponse] = Field(default_factory=list)


class ProjectPageResponse(BaseModel):
    items: list[ProjectResponse]
    next_cursor: str | None
    has_next_page: bool
