"""Pydantic schemas for the Job domain."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import JobStatus


class JobBase(BaseModel):
    """Base fields for a Job."""

    job_type: str = Field(..., min_length=1, max_length=100, description="Type of background job")
    payload: dict[str, Any] | None = Field(default=None, description="Job configuration/input payload")

    @field_validator("job_type", mode="before")
    @classmethod
    def strip_and_validate_job_type(cls, v: str) -> str:
        """Strip whitespace and reject blank job types."""
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Job type must not be blank")
        return v


class JobCreate(JobBase):
    """Schema for creating a new job."""

    project_id: uuid.UUID = Field(..., description="Target project UUID")


class JobStatusUpdate(BaseModel):
    """Schema for requesting a job lifecycle status transition."""

    status: JobStatus = Field(..., description="Target lifecycle status")
    error_message: str | None = Field(default=None, description="Error message if transitioning to FAILED")


class JobResponse(BaseModel):
    """Schema for returning a job to the client."""

    id: uuid.UUID
    project_id: uuid.UUID
    job_type: str
    status: JobStatus
    payload: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
