from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import ApplicationRole, ProvisioningStatus


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    email: str
    role: ApplicationRole


class EmployeeAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    display_name: str
    email: str
    role: ApplicationRole
    active: bool
    provisioning_status: ProvisioningStatus
    created_at: datetime
    updated_at: datetime
    version: int


class EmployeePageResponse(BaseModel):
    items: list[EmployeeAdminResponse]
    next_cursor: str | None
    has_next_page: bool


class ProvisionEmployeeRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=100)
    username: str = Field(min_length=3, max_length=100)
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=2, max_length=200)
    role: ApplicationRole
    active: bool = True
    temporary_password: str = Field(min_length=12, max_length=200)


class RoleUpdateRequest(BaseModel):
    role: ApplicationRole


class ActiveUpdateRequest(BaseModel):
    active: bool
