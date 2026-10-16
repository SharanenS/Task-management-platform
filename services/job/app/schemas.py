from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import JobStatus, JobType


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectTaskExportPayload(StrictModel):
    project_id: UUID
    format: Literal["CSV"] = "CSV"
    include_completed: bool = True


class JobSubmissionRequest(StrictModel):
    job_type: Literal[JobType.PROJECT_TASK_EXPORT]
    payload: ProjectTaskExportPayload
    idempotency_key: str = Field(min_length=16, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    job_type: JobType
    status: JobStatus
    submitter_employee_id: UUID
    related_project_id: UUID | None
    payload: dict[str, object]
    result_summary: str | None
    failure_classification: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class JobPageResponse(BaseModel):
    items: list[JobResponse]
    next_cursor: str | None
    has_next_page: bool


class JobAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    attempt_number: int
    status: JobStatus
    created_at: datetime


class JobAttemptPageResponse(BaseModel):
    items: list[JobAttemptResponse]
    next_cursor: str | None = None
    has_next_page: bool = False
