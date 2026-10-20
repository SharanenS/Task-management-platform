import hmac
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.admin_service import (
    AdminError,
    get_employee_detail,
    list_eligible_employees,
    list_employees,
    provision_employee,
    reconcile_employee,
    require_active_employee,
    resolve_employee_references,
    set_employee_active,
    update_role,
)
from app.config import settings
from app.db import get_session
from app.models import ApplicationRole, Employee
from app.schemas import (
    ActiveUpdateRequest,
    EligibleEmployeePageResponse,
    EligibleEmployeeResponse,
    EmployeeAdminResponse,
    EmployeePageResponse,
    EmployeeReferenceRequest,
    EmployeeResponse,
    ProvisionEmployeeRequest,
    RoleUpdateRequest,
)

app = FastAPI(title="Employee Service", docs_url=None, redoc_url=None, openapi_url=None)
SessionDependency = Annotated[Session, Depends(get_session)]


def require_internal_service(x_internal_service_key: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_internal_service_key, settings.internal_service_key):
        raise HTTPException(status_code=403, detail="Forbidden")


def require_job_worker(x_job_worker_service_key: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_job_worker_service_key, settings.job_worker_service_key):
        raise HTTPException(status_code=403, detail="Forbidden")


def actor_subject(x_actor_subject: str = Header(default="")) -> str:
    if not x_actor_subject:
        raise HTTPException(status_code=403, detail="Forbidden")
    return x_actor_subject


ActorSubject = Annotated[str, Depends(actor_subject)]


def admin_failure(error: AdminError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": error.message},
    )


def admin_response(employee: Employee) -> EmployeeAdminResponse:
    return EmployeeAdminResponse(
        id=str(employee.id),
        username=employee.username,
        display_name=employee.display_name,
        email=employee.email,
        role=employee.role,
        active=employee.active,
        provisioning_status=employee.provisioning_status,
        created_at=employee.created_at,
        updated_at=employee.updated_at,
        version=employee.version,
    )


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def readiness(session: SessionDependency) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get(
    "/internal/execution/employees/{employee_id}",
    dependencies=[Depends(require_job_worker)],
)
def execution_employee(employee_id: UUID, session: SessionDependency) -> dict[str, str | bool]:
    employee = session.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not available")
    return {"id": str(employee.id), "role": employee.role.value, "active": employee.active}


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


@app.get(
    "/internal/project-members/eligible",
    response_model=EligibleEmployeePageResponse,
    dependencies=[Depends(require_internal_service)],
)
def eligible_project_members(
    session: SessionDependency,
    actor: ActorSubject,
    first: int = Query(default=20, ge=1, le=25),
    after: str | None = None,
    search: str | None = Query(default=None, max_length=200),
) -> EligibleEmployeePageResponse:
    try:
        page = list_eligible_employees(session, actor, first=first, after=after, search=search)
    except AdminError as error:
        raise admin_failure(error) from error
    return EligibleEmployeePageResponse(
        items=[
            EligibleEmployeeResponse(
                id=str(employee.id), display_name=employee.display_name, email=employee.email
            )
            for employee in page.items
        ],
        next_cursor=page.next_cursor,
        has_next_page=page.has_next_page,
    )


@app.get(
    "/internal/project-members/{employee_id}/validate",
    response_model=EligibleEmployeeResponse,
    dependencies=[Depends(require_internal_service)],
)
def validate_project_member(
    employee_id: UUID, session: SessionDependency, actor: ActorSubject
) -> EligibleEmployeeResponse:
    try:
        employee = require_active_employee(session, actor, employee_id)
    except AdminError as error:
        raise admin_failure(error) from error
    return EligibleEmployeeResponse(
        id=str(employee.id), display_name=employee.display_name, email=employee.email
    )


@app.post(
    "/internal/project-members/resolve",
    response_model=list[EligibleEmployeeResponse],
    dependencies=[Depends(require_internal_service)],
)
def resolve_project_members(
    body: EmployeeReferenceRequest, session: SessionDependency, actor: ActorSubject
) -> list[EligibleEmployeeResponse]:
    try:
        employees = resolve_employee_references(session, actor, body.employee_ids)
    except AdminError as error:
        raise admin_failure(error) from error
    return [
        EligibleEmployeeResponse(
            id=str(employee.id), display_name=employee.display_name, email=employee.email
        )
        for employee in employees
    ]


@app.get(
    "/internal/admin/employees",
    response_model=EmployeePageResponse,
    dependencies=[Depends(require_internal_service)],
)
def employee_directory(
    session: SessionDependency,
    actor: ActorSubject,
    first: int = Query(default=20, ge=1, le=50),
    after: str | None = None,
    search: str | None = Query(default=None, max_length=200),
    role: ApplicationRole | None = None,
    active: bool | None = None,
) -> EmployeePageResponse:
    try:
        page = list_employees(
            session, actor, first=first, after=after, search=search, role=role, active=active
        )
    except AdminError as error:
        raise admin_failure(error) from error
    return EmployeePageResponse(
        items=[admin_response(employee) for employee in page.items],
        next_cursor=page.next_cursor,
        has_next_page=page.has_next_page,
    )


@app.get(
    "/internal/admin/employees/{employee_id}",
    response_model=EmployeeAdminResponse,
    dependencies=[Depends(require_internal_service)],
)
def employee_detail(
    employee_id: UUID, session: SessionDependency, actor: ActorSubject
) -> EmployeeAdminResponse:
    try:
        return admin_response(get_employee_detail(session, actor, employee_id))
    except AdminError as error:
        raise admin_failure(error) from error


@app.post(
    "/internal/admin/employees",
    response_model=EmployeeAdminResponse,
    dependencies=[Depends(require_internal_service)],
)
def provision(
    body: ProvisionEmployeeRequest, session: SessionDependency, actor: ActorSubject
) -> EmployeeAdminResponse:
    try:
        employee = provision_employee(
            session,
            actor,
            idempotency_key=body.idempotency_key,
            username=body.username,
            email=body.email,
            display_name=body.display_name,
            role=body.role,
            active=body.active,
            temporary_password=body.temporary_password,
        )
        return admin_response(employee)
    except AdminError as error:
        raise admin_failure(error) from error


@app.put(
    "/internal/admin/employees/{employee_id}/role",
    response_model=EmployeeAdminResponse,
    dependencies=[Depends(require_internal_service)],
)
def change_role(
    employee_id: UUID,
    body: RoleUpdateRequest,
    session: SessionDependency,
    actor: ActorSubject,
) -> EmployeeAdminResponse:
    try:
        return admin_response(update_role(session, actor, employee_id, body.role))
    except AdminError as error:
        raise admin_failure(error) from error


@app.put(
    "/internal/admin/employees/{employee_id}/active",
    response_model=EmployeeAdminResponse,
    dependencies=[Depends(require_internal_service)],
)
def change_active(
    employee_id: UUID,
    body: ActiveUpdateRequest,
    session: SessionDependency,
    actor: ActorSubject,
) -> EmployeeAdminResponse:
    try:
        return admin_response(set_employee_active(session, actor, employee_id, body.active))
    except AdminError as error:
        raise admin_failure(error) from error


@app.post(
    "/internal/admin/employees/{employee_id}/reconcile",
    response_model=EmployeeAdminResponse,
    dependencies=[Depends(require_internal_service)],
)
def reconcile(
    employee_id: UUID, session: SessionDependency, actor: ActorSubject
) -> EmployeeAdminResponse:
    try:
        return admin_response(reconcile_employee(session, actor, employee_id))
    except AdminError as error:
        raise admin_failure(error) from error
