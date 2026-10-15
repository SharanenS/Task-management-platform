from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import (
    ProjectRole,
    ProjectStatus,
    TaskActivityType,
    TaskPriority,
    TaskStatus,
)


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


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=8000)
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_employee_id: UUID | None = None
    due_date: date | None = None

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return " ".join(value.split())


class TaskUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=8000)
    priority: TaskPriority
    due_date: date | None = None
    expected_version: int = Field(ge=1)

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return " ".join(value.split())


class TaskAssignmentRequest(BaseModel):
    assignee_employee_id: UUID | None
    expected_version: int = Field(ge=1)


class TaskStatusRequest(BaseModel):
    status: TaskStatus
    expected_version: int = Field(ge=1)


class TaskCommentCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body", mode="before")
    @classmethod
    def normalize_body(cls, value: str) -> str:
        return value.strip()


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    number: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    assignee_employee_id: UUID | None
    creator_employee_id: UUID
    due_date: date | None
    version: int
    created_at: datetime
    updated_at: datetime


class TaskPageResponse(BaseModel):
    items: list[TaskResponse]
    next_cursor: str | None
    has_next_page: bool


class TaskLaneResponse(BaseModel):
    status: TaskStatus
    items: list[TaskResponse]
    has_more: bool


class TaskBoardResponse(BaseModel):
    lanes: list[TaskLaneResponse]


class TaskCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    task_id: UUID
    author_employee_id: UUID
    body: str
    created_at: datetime


class TaskCommentPageResponse(BaseModel):
    items: list[TaskCommentResponse]
    next_cursor: str | None
    has_next_page: bool


class TaskActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    task_id: UUID
    actor_employee_id: UUID
    activity_type: TaskActivityType
    change_data: dict[str, str | int | None]
    created_at: datetime


class TaskActivityPageResponse(BaseModel):
    items: list[TaskActivityResponse]
    next_cursor: str | None
    has_next_page: bool
