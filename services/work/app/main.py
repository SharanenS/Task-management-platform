import hmac
import time
from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.models import ProjectStatus, Task, TaskPriority, TaskStatus
from app.observability import (
    correlation_id_ctx,
    format_traceparent,
    metrics,
    parse_traceparent,
    telemetry,
    validate_correlation_id,
)
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
    WorkDashboardResponse,
    WorkOutboxSummaryResponse,
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
    get_dashboard_metrics,
    get_operations_summary,
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


def require_job_worker(x_job_worker_service_key: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_job_worker_service_key, settings.job_worker_service_key):
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


@app.middleware("http")
async def request_metadata(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    raw_corr_id = request.headers.get("x-correlation-id") or request.headers.get("X-Correlation-ID")
    correlation_id = validate_correlation_id(raw_corr_id)
    token_corr = correlation_id_ctx.set(correlation_id)

    raw_tp = request.headers.get("traceparent")
    parsed_tp = parse_traceparent(raw_tp)
    parent_trace_id = parsed_tp[0] if parsed_tp else None
    parent_span_id = parsed_tp[1] if parsed_tp else None

    path = request.url.path
    if path.startswith("/health/"):
        path_label = path
    elif path == "/metrics":
        path_label = "/metrics"
    elif path.startswith("/internal/"):
        path_label = "/internal"
    else:
        path_label = "other"

    span = telemetry.start_span(
        "http_request",
        parent_trace_id=parent_trace_id,
        parent_span_id=parent_span_id,
        attributes={"http.method": request.method, "http.route": path_label},
    )

    request_id = str(uuid4())
    started = time.monotonic()

    with span:
        try:
            response = await call_next(request)
            duration_s = time.monotonic() - started
            duration_ms = round(duration_s * 1000, 2)

            span.set_attribute("http.status_code", response.status_code)
            if response.status_code >= 500:
                span.set_status("ERROR")

            status_str = str(response.status_code)
            metrics.counter(
                "http_requests_total",
                labels={"method": request.method, "status": status_str, "path": path_label},
                help_text="Total number of HTTP requests processed",
            )
            metrics.histogram(
                "http_request_duration_seconds",
                duration_s,
                labels={"method": request.method, "status": status_str},
                help_text="HTTP request duration in seconds",
            )

            response.headers["X-Request-ID"] = request_id
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["traceparent"] = format_traceparent(span.trace_id, span.span_id)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Cache-Control"] = "no-store"

            outcome = "success" if response.status_code < 400 else "failure"
            telemetry.logger.log(
                "INFO" if response.status_code < 500 else "ERROR",
                "http_request",
                outcome=outcome,
                request_id=request_id,
                method=request.method,
                path=path_label,
                status=response.status_code,
                duration_ms=duration_ms,
            )
            return response
        except Exception as exc:
            duration_s = time.monotonic() - started
            span.set_status("ERROR")
            span.set_attribute("http.status_code", 500)
            metrics.counter(
                "http_requests_total",
                labels={"method": request.method, "status": "500", "path": path_label},
            )
            telemetry.logger.error(
                "http_request",
                outcome="error",
                error_code=exc.__class__.__name__,
                request_id=request_id,
                method=request.method,
                path=path_label,
                status=500,
            )
            raise
        finally:
            correlation_id_ctx.reset(token_corr)


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def readiness(session: SessionDependency) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get("/metrics")
def prometheus_metrics() -> Response:
    return Response(
        content=metrics.render_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get(
    "/internal/operations/summary",
    response_model=WorkOutboxSummaryResponse,
    dependencies=[Depends(require_internal_service)],
)
def operations_summary(session: SessionDependency) -> WorkOutboxSummaryResponse:
    return get_operations_summary(session)


@app.get(
    "/internal/execution/projects/{project_id}/tasks",
    dependencies=[Depends(require_job_worker)],
)
def execution_tasks(
    project_id: UUID,
    session: SessionDependency,
    actor: ActorDependency,
    include_completed: bool = True,
    limit: int = Query(default=500, ge=1, le=500),
) -> dict[str, object]:
    try:
        project = get_project(session, actor, project_id)
    except WorkError as error:
        raise failure(error) from error
    statement = select(Task).where(Task.project_id == project.id)
    if not include_completed:
        statement = statement.where(Task.status != TaskStatus.DONE)
    tasks = list(session.scalars(statement.order_by(Task.number).limit(limit + 1)))
    truncated = len(tasks) > limit
    tasks = tasks[:limit]
    return {
        "projectKey": project.key,
        "truncated": truncated,
        "items": [
            {
                "reference": f"{project.key}-{task.number}",
                "title": task.title,
                "status": task.status.value,
                "priority": task.priority.value,
                "assigneeDisplayName": "",
                "dueDate": task.due_date.isoformat() if task.due_date else "",
            }
            for task in tasks
        ],
    }


@app.get(
    "/internal/dashboard/metrics",
    response_model=WorkDashboardResponse,
    dependencies=[Depends(require_internal_service)],
)
def dashboard_metrics(session: SessionDependency, actor: ActorDependency) -> WorkDashboardResponse:
    try:
        return get_dashboard_metrics(session, actor)
    except WorkError as error:
        raise failure(error) from error


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
