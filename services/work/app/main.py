import hmac
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.models import ProjectStatus
from app.schemas import (
    MembershipCreateRequest,
    MembershipRoleRequest,
    ProjectCreateRequest,
    ProjectPageResponse,
    ProjectResponse,
    ProjectStatusRequest,
    ProjectUpdateRequest,
)
from app.service import (
    Actor,
    WorkError,
    add_member,
    change_member_role,
    create_project,
    get_project,
    list_projects,
    remove_member,
    set_status,
    update_project,
)

app = FastAPI(title="Work Service", docs_url=None, redoc_url=None, openapi_url=None)
SessionDependency = Annotated[Session, Depends(get_session)]


def require_internal_service(x_internal_service_key: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_internal_service_key, settings.internal_service_key):
        raise HTTPException(status_code=403, detail="Forbidden")


def actor_context(
    x_actor_employee_id: str = Header(default=""),
    x_actor_application_role: str = Header(default=""),
) -> Actor:
    try:
        employee_id = UUID(x_actor_employee_id)
    except ValueError as error:
        raise HTTPException(status_code=403, detail="Forbidden") from error
    if x_actor_application_role not in {"ADMIN", "MANAGER", "MEMBER"}:
        raise HTTPException(status_code=403, detail="Forbidden")
    return Actor(employee_id, x_actor_application_role)


ActorDependency = Annotated[Actor, Depends(actor_context)]


def failure(error: WorkError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code, detail={"code": error.code, "message": error.message}
    )


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def readiness(session: SessionDependency) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get(
    "/internal/projects",
    response_model=ProjectPageResponse,
    dependencies=[Depends(require_internal_service)],
)
def project_directory(
    session: SessionDependency,
    actor: ActorDependency,
    first: int = Query(default=20, ge=1, le=50),
    after: str | None = None,
    search: str | None = Query(default=None, max_length=200),
    status: ProjectStatus | None = None,
) -> ProjectPageResponse:
    try:
        page = list_projects(session, actor, first=first, after=after, search=search, status=status)
        return ProjectPageResponse(
            items=[ProjectResponse.model_validate(item) for item in page.items],
            next_cursor=page.next_cursor,
            has_next_page=page.has_next_page,
        )
    except WorkError as error:
        raise failure(error) from error


@app.get(
    "/internal/projects/{project_id}",
    response_model=ProjectResponse,
    dependencies=[Depends(require_internal_service)],
)
def project_detail(
    project_id: UUID, session: SessionDependency, actor: ActorDependency
) -> ProjectResponse:
    try:
        return ProjectResponse.model_validate(get_project(session, actor, project_id))
    except WorkError as error:
        raise failure(error) from error


@app.post(
    "/internal/projects",
    response_model=ProjectResponse,
    dependencies=[Depends(require_internal_service)],
)
def create(
    body: ProjectCreateRequest, session: SessionDependency, actor: ActorDependency
) -> ProjectResponse:
    try:
        return ProjectResponse.model_validate(create_project(session, actor, **body.model_dump()))
    except WorkError as error:
        raise failure(error) from error


@app.put(
    "/internal/projects/{project_id}",
    response_model=ProjectResponse,
    dependencies=[Depends(require_internal_service)],
)
def update(
    project_id: UUID,
    body: ProjectUpdateRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> ProjectResponse:
    try:
        return ProjectResponse.model_validate(
            update_project(session, actor, project_id, **body.model_dump())
        )
    except WorkError as error:
        raise failure(error) from error


@app.put(
    "/internal/projects/{project_id}/status",
    response_model=ProjectResponse,
    dependencies=[Depends(require_internal_service)],
)
def status_change(
    project_id: UUID,
    body: ProjectStatusRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> ProjectResponse:
    try:
        return ProjectResponse.model_validate(
            set_status(session, actor, project_id, **body.model_dump())
        )
    except WorkError as error:
        raise failure(error) from error


@app.post(
    "/internal/projects/{project_id}/members",
    response_model=ProjectResponse,
    dependencies=[Depends(require_internal_service)],
)
def add(
    project_id: UUID,
    body: MembershipCreateRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> ProjectResponse:
    try:
        return ProjectResponse.model_validate(
            add_member(session, actor, project_id, body.employee_id, body.role)
        )
    except WorkError as error:
        raise failure(error) from error


@app.put(
    "/internal/projects/{project_id}/members/{employee_id}",
    response_model=ProjectResponse,
    dependencies=[Depends(require_internal_service)],
)
def change_role(
    project_id: UUID,
    employee_id: UUID,
    body: MembershipRoleRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> ProjectResponse:
    try:
        return ProjectResponse.model_validate(
            change_member_role(session, actor, project_id, employee_id, body.role)
        )
    except WorkError as error:
        raise failure(error) from error


@app.delete(
    "/internal/projects/{project_id}/members/{employee_id}",
    response_model=ProjectResponse,
    dependencies=[Depends(require_internal_service)],
)
def remove(
    project_id: UUID,
    employee_id: UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> ProjectResponse:
    try:
        return ProjectResponse.model_validate(
            remove_member(session, actor, project_id, employee_id)
        )
    except WorkError as error:
        raise failure(error) from error
