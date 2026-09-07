"""User-related Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role_names: list[str] = Field(default=["member"])


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    email: EmailStr | None = None
    is_active: bool | None = None
    role_names: list[str] | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    is_active: bool
    roles: list[str]
    permissions: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int