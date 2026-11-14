from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import ActionType, ExecutionStatus, TriggerType


class RuleCreate(BaseModel):
    project_id: UUID
    name: str = Field(min_length=1, max_length=200)
    trigger_type: TriggerType
    action_type: ActionType
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("name required")
        return normalized


class RuleUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    expected_version: int = Field(ge=1)


class RuleStateUpdate(BaseModel):
    enabled: bool
    expected_version: int = Field(ge=1)


class RuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    name: str
    trigger_type: TriggerType
    action_type: ActionType
    enabled: bool
    creator_employee_id: UUID
    version: int
    created_at: datetime
    updated_at: datetime


class RulePage(BaseModel):
    items: list[RuleResponse]
    next_cursor: str | None
    has_next_page: bool


class ExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    rule_id: UUID
    source_event_id: UUID
    project_id: UUID
    task_id: UUID
    status: ExecutionStatus
    resulting_job_id: UUID | None
    failure_classification: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class ExecutionPage(BaseModel):
    items: list[ExecutionResponse]
    next_cursor: str | None
    has_next_page: bool
