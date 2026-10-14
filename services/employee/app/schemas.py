from pydantic import BaseModel, ConfigDict

from app.models import ApplicationRole


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    email: str
    role: ApplicationRole
