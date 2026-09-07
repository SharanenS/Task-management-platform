"""Report-related Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class ReportCreate(BaseModel):
    project_id: uuid.UUID


class ReportResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    requested_by: uuid.UUID
    status: str
    file_url: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}