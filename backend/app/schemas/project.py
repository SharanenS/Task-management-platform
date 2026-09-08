"""Pydantic schemas for the Project domain."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import ProjectStatus


class ProjectBase(BaseModel):
    """Base fields for a Project."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: str | None = Field(default=None, description="Optional project description")


class ProjectCreate(ProjectBase):
    """Schema for creating a new project. owner_id is NOT client-controllable."""

    status: ProjectStatus = Field(
        default=ProjectStatus.PLANNING,
        description="Initial status of the project",
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_and_validate_name(cls, v: str) -> str:
        """Strip whitespace and reject names that become empty."""
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Project name must not be blank")
        return v


class ProjectUpdate(BaseModel):
    """Schema for updating an existing project."""

    name: str | None = Field(default=None, min_length=1, max_length=255, description="Updated project name")
    description: str | None = Field(default=None, description="Updated project description")
    status: ProjectStatus | None = Field(default=None, description="Updated project status")

    @field_validator("name", mode="before")
    @classmethod
    def strip_and_validate_name(cls, v: str | None) -> str | None:
        """Strip whitespace and reject names that become empty."""
        if v is not None and isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Project name must not be blank")
        return v


class ProjectResponse(ProjectBase):
    """Schema for returning a project to the client."""

    id: uuid.UUID
    status: ProjectStatus
    owner_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
