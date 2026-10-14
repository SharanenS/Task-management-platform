import hmac
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.models import Employee
from app.schemas import EmployeeResponse

app = FastAPI(title="Employee Service", docs_url=None, redoc_url=None, openapi_url=None)
SessionDependency = Annotated[Session, Depends(get_session)]


def require_internal_service(x_internal_service_key: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_internal_service_key, settings.internal_service_key):
        raise HTTPException(status_code=403, detail="Forbidden")


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def readiness(session: SessionDependency) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get(
    "/internal/employees/by-subject/{subject}",
    response_model=EmployeeResponse,
    dependencies=[Depends(require_internal_service)],
)
def employee_by_subject(subject: str, session: SessionDependency) -> EmployeeResponse:
    employee = session.scalar(select(Employee).where(Employee.keycloak_subject == subject))
    if employee is None or not employee.active:
        raise HTTPException(status_code=404, detail="Employee not available")
    return EmployeeResponse(
        id=str(employee.id),
        display_name=employee.display_name,
        email=employee.email,
        role=employee.role,
    )
