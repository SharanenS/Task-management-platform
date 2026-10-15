import hmac
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.models import ProjectStatus, TaskPriority, TaskStatus
from app.schemas import (
    MembershipCreateRequest,
    MembershipRoleRequest,
    ProjectCreateRequest,
    ProjectPageResponse,
    ProjectResponse,
    ProjectStatusRequest,
    ProjectUpdateRequest,
    TaskActivityPageResponse,
    TaskActivityResponse,
    TaskAssignmentRequest,
    TaskBoardResponse,
    TaskCommentCreateRequest,
    TaskCommentPageResponse,
    TaskCommentResponse,
    TaskCreateRequest,
    TaskLaneResponse,
    TaskPageResponse,
    TaskResponse,
    TaskStatusRequest,
    TaskUpdateRequest,
)
from app.service import (
    Actor,
    WorkError,
    add_member,
    add_task_comment,
    assign_task,
    change_member_role,
    change_task_status,
    create_project,
    create_task,
    get_project,
    get_task,
    list_projects,
    list_task_activity,
    list_task_comments,
    list_tasks,
    remove_member,
    set_status,
    task_board,
    update_project,
    update_task,
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


@app.get(
    "/internal/projects/{project_id}/tasks",
    response_model=TaskPageResponse,
    dependencies=[Depends(require_internal_service)],
)
def task_directory(
    project_id: UUID,
    session: SessionDependency,
    actor: ActorDependency,
    first: int = Query(default=20, ge=1, le=50),
    after: str | None = None,
    search: str | None = Query(default=None, max_length=200),
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    assignee_employee_id: UUID | None = None,
    unassigned: bool = False,
) -> TaskPageResponse:
    try:
        page = list_tasks(
            session,
            actor,
            project_id,
            first=first,
            after=after,
            search=search,
            status=status,
            priority=priority,
            assignee_employee_id=assignee_employee_id,
            unassigned=unassigned,
        )
        return TaskPageResponse(
            items=[TaskResponse.model_validate(item) for item in page.items],
            next_cursor=page.next_cursor,
            has_next_page=page.has_next_page,
        )
    except WorkError as error:
        raise failure(error) from error


@app.get(
    "/internal/projects/{project_id}/task-board",
    response_model=TaskBoardResponse,
    dependencies=[Depends(require_internal_service)],
)
def board(
    project_id: UUID,
    session: SessionDependency,
    actor: ActorDependency,
    lane_size: int = Query(default=20, ge=1, le=25),
) -> TaskBoardResponse:
    try:
        lanes = task_board(session, actor, project_id, lane_size=lane_size)
        return TaskBoardResponse(
            lanes=[
                TaskLaneResponse(
                    status=status,
                    items=[TaskResponse.model_validate(item) for item in items],
                    has_more=has_more,
                )
                for status, (items, has_more) in lanes.items()
            ]
        )
    except WorkError as error:
        raise failure(error) from error


@app.get(
    "/internal/projects/{project_id}/tasks/{task_id}",
    response_model=TaskResponse,
    dependencies=[Depends(require_internal_service)],
)
def task_detail(
    project_id: UUID, task_id: UUID, session: SessionDependency, actor: ActorDependency
) -> TaskResponse:
    try:
        return TaskResponse.model_validate(get_task(session, actor, project_id, task_id))
    except WorkError as error:
        raise failure(error) from error


@app.post(
    "/internal/projects/{project_id}/tasks",
    response_model=TaskResponse,
    dependencies=[Depends(require_internal_service)],
)
def task_create(
    project_id: UUID,
    body: TaskCreateRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> TaskResponse:
    try:
        return TaskResponse.model_validate(
            create_task(session, actor, project_id, **body.model_dump())
        )
    except WorkError as error:
        raise failure(error) from error


@app.put(
    "/internal/projects/{project_id}/tasks/{task_id}",
    response_model=TaskResponse,
    dependencies=[Depends(require_internal_service)],
)
def task_update(
    project_id: UUID,
    task_id: UUID,
    body: TaskUpdateRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> TaskResponse:
    try:
        return TaskResponse.model_validate(
            update_task(session, actor, project_id, task_id, **body.model_dump())
        )
    except WorkError as error:
        raise failure(error) from error


@app.put(
    "/internal/projects/{project_id}/tasks/{task_id}/assignment",
    response_model=TaskResponse,
    dependencies=[Depends(require_internal_service)],
)
def task_assignment(
    project_id: UUID,
    task_id: UUID,
    body: TaskAssignmentRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> TaskResponse:
    try:
        return TaskResponse.model_validate(
            assign_task(session, actor, project_id, task_id, **body.model_dump())
        )
    except WorkError as error:
        raise failure(error) from error


@app.put(
    "/internal/projects/{project_id}/tasks/{task_id}/status",
    response_model=TaskResponse,
    dependencies=[Depends(require_internal_service)],
)
def task_status_change(
    project_id: UUID,
    task_id: UUID,
    body: TaskStatusRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> TaskResponse:
    try:
        return TaskResponse.model_validate(
            change_task_status(session, actor, project_id, task_id, **body.model_dump())
        )
    except WorkError as error:
        raise failure(error) from error


@app.get(
    "/internal/projects/{project_id}/tasks/{task_id}/comments",
    response_model=TaskCommentPageResponse,
    dependencies=[Depends(require_internal_service)],
)
def task_comments(
    project_id: UUID,
    task_id: UUID,
    session: SessionDependency,
    actor: ActorDependency,
    first: int = Query(default=20, ge=1, le=50),
    after: str | None = None,
) -> TaskCommentPageResponse:
    try:
        page = list_task_comments(session, actor, project_id, task_id, first=first, after=after)
        return TaskCommentPageResponse(
            items=[TaskCommentResponse.model_validate(item) for item in page.items],
            next_cursor=page.next_cursor,
            has_next_page=page.has_next_page,
        )
    except WorkError as error:
        raise failure(error) from error


@app.post(
    "/internal/projects/{project_id}/tasks/{task_id}/comments",
    response_model=TaskCommentResponse,
    dependencies=[Depends(require_internal_service)],
)
def task_comment_add(
    project_id: UUID,
    task_id: UUID,
    body: TaskCommentCreateRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> TaskCommentResponse:
    try:
        return TaskCommentResponse.model_validate(
            add_task_comment(session, actor, project_id, task_id, body=body.body)
        )
    except WorkError as error:
        raise failure(error) from error


@app.get(
    "/internal/projects/{project_id}/tasks/{task_id}/activity",
    response_model=TaskActivityPageResponse,
    dependencies=[Depends(require_internal_service)],
)
def task_activity(
    project_id: UUID,
    task_id: UUID,
    session: SessionDependency,
    actor: ActorDependency,
    first: int = Query(default=20, ge=1, le=50),
    after: str | None = None,
) -> TaskActivityPageResponse:
    try:
        page = list_task_activity(session, actor, project_id, task_id, first=first, after=after)
        return TaskActivityPageResponse(
            items=[TaskActivityResponse.model_validate(item) for item in page.items],
            next_cursor=page.next_cursor,
            has_next_page=page.has_next_page,
        )
    except WorkError as error:
        raise failure(error) from error
