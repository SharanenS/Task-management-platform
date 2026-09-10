"""Pydantic schemas for the Outbox domain."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import OutboxStatus


class OutboxEventResponse(BaseModel):
    """Schema representing an outbox event."""

    id: uuid.UUID
    event_type: str = Field(..., description="Event identifier string, e.g. JOB_CREATED")
    aggregate_type: str = Field(..., description="Entity aggregate type, e.g. JOB")
    aggregate_id: uuid.UUID = Field(..., description="Target aggregate UUID")
    payload: dict[str, Any] = Field(..., description="Minimal message payload")
    status: OutboxStatus
    attempt_count: int
    available_at: datetime
    last_error: str | None = None
    published_at: datetime | None = None
    claimed_at: datetime | None = None
    lease_until: datetime | None = None
    claim_owner: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
