from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models import JobStatus, JobType, PublicationStatus


class PublicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    job_id: UUID
    status: PublicationStatus
    attempt_count: int
    available_at: datetime
    lease_expires_at: datetime | None
    published_at: datetime | None
    last_failure_classification: str | None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reconciliation_required(self) -> bool:
        return self.status == PublicationStatus.RECONCILIATION_REQUIRED


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


class JobDispatchRequest(StrictModel):
    expected_version: int = Field(ge=1)


class JobRetryRequest(StrictModel):
    expected_version: int = Field(ge=1)


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    job_type: JobType
    status: JobStatus
    submitter_employee_id: UUID
    related_project_id: UUID | None
    payload: dict[str, object]
    result_summary: str | None
    result_content: str | None
    result_content_type: str | None
    result_checksum: str | None
    result_row_count: int | None
    result_truncated: bool | None
    failure_classification: str | None
    completed_at: datetime | None
    execution_generation: int
    retry_exhausted: bool
    manual_retry_count: int
    version: int
    created_at: datetime
    updated_at: datetime
    publication: PublicationResponse | None


class JobPageResponse(BaseModel):
    items: list[JobResponse]
    next_cursor: str | None
    has_next_page: bool


class PublicationPageResponse(BaseModel):
    items: list[PublicationResponse]
    next_cursor: str | None
    has_next_page: bool


class JobAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    attempt_number: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    failure_code: str | None
    retryable: bool
    safe_summary: str | None
    lease_acquired_at: datetime | None
    lease_expires_at: datetime | None
    last_heartbeat_at: datetime | None
    abandoned_at: datetime | None
    retry_scheduled_at: datetime | None
    recovered_at: datetime | None


class JobAttemptPageResponse(BaseModel):
    items: list[JobAttemptResponse]
    next_cursor: str | None = None
    has_next_page: bool = False
