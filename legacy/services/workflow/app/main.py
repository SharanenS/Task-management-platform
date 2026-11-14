import hmac
import time
from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.observability import (
    correlation_id_ctx,
    format_traceparent,
    metrics,
    parse_traceparent,
    telemetry,
    validate_correlation_id,
)
from app.schemas import (
    ExecutionPage,
    ExecutionResponse,
    RuleCreate,
    RulePage,
    RuleResponse,
    RuleStateUpdate,
    RuleUpdate,
)
from app.service import (
    Actor,
    WorkflowError,
    create_rule,
    get_execution,
    get_rule,
    list_executions,
    list_rules,
    update_rule,
)

app = FastAPI(title="Workflow Service", docs_url=None, redoc_url=None, openapi_url=None)
SessionDependency = Annotated[Session, Depends(get_session)]


def require_internal(x_internal_service_key: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_internal_service_key, settings.internal_service_key):
        raise HTTPException(403, "Forbidden")


def actor_context(
    x_actor_employee_id: str = Header(default=""),
    x_actor_application_role: str = Header(default=""),
) -> Actor:
    try:
        identifier = UUID(x_actor_employee_id)
    except ValueError as error:
        raise HTTPException(403, "Forbidden") from error
    if x_actor_application_role not in {"ADMIN", "MANAGER", "MEMBER"}:
        raise HTTPException(403, "Forbidden")
    return Actor(identifier, x_actor_application_role)


ActorDependency = Annotated[Actor, Depends(actor_context)]


def ids(value: str | None) -> set[UUID]:
    if not value:
        return set()
    try:
        return {UUID(item) for item in value.split(",") if item}
    except ValueError as error:
        raise HTTPException(403, "Forbidden") from error


def failure(error: WorkflowError) -> HTTPException:
    return HTTPException(error.status_code, {"code": error.code, "message": error.message})


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
def live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def ready(session: SessionDependency) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get("/metrics")
def prometheus_metrics() -> Response:
    return Response(
        content=metrics.render_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/internal/rules", response_model=RulePage, dependencies=[Depends(require_internal)])
def rules(
    session: SessionDependency,
    actor: ActorDependency,
    first: int = Query(20, ge=1, le=50),
    after: str | None = None,
    project_id: UUID | None = None,
    enabled: bool | None = None,
    x_actor_project_ids: str | None = Header(default=None),
) -> RulePage:
    try:
        page = list_rules(
            session,
            actor,
            project_ids=ids(x_actor_project_ids),
            first=first,
            after=after,
            project_id=project_id,
            enabled=enabled,
        )
        return RulePage(
            items=[RuleResponse.model_validate(item) for item in page.items],
            next_cursor=page.next_cursor,
            has_next_page=page.has_next_page,
        )
    except WorkflowError as error:
        raise failure(error) from error


@app.get(
    "/internal/rules/{rule_id}",
    response_model=RuleResponse,
    dependencies=[Depends(require_internal)],
)
def rule(
    rule_id: UUID,
    session: SessionDependency,
    actor: ActorDependency,
    x_actor_project_ids: str | None = Header(default=None),
) -> RuleResponse:
    try:
        return RuleResponse.model_validate(
            get_rule(session, actor, rule_id, ids(x_actor_project_ids))
        )
    except WorkflowError as error:
        raise failure(error) from error


@app.post("/internal/rules", response_model=RuleResponse, dependencies=[Depends(require_internal)])
def create(
    body: RuleCreate,
    session: SessionDependency,
    actor: ActorDependency,
    x_actor_managed_project_ids: str | None = Header(default=None),
) -> RuleResponse:
    try:
        return RuleResponse.model_validate(
            create_rule(session, actor, body, ids(x_actor_managed_project_ids))
        )
    except WorkflowError as error:
        raise failure(error) from error


@app.put(
    "/internal/rules/{rule_id}",
    response_model=RuleResponse,
    dependencies=[Depends(require_internal)],
)
def update(
    rule_id: UUID,
    body: RuleUpdate,
    session: SessionDependency,
    actor: ActorDependency,
    x_actor_managed_project_ids: str | None = Header(default=None),
) -> RuleResponse:
    try:
        return RuleResponse.model_validate(
            update_rule(
                session,
                actor,
                rule_id,
                name=body.name,
                enabled=None,
                expected_version=body.expected_version,
                managed_project_ids=ids(x_actor_managed_project_ids),
            )
        )
    except WorkflowError as error:
        raise failure(error) from error


@app.put(
    "/internal/rules/{rule_id}/state",
    response_model=RuleResponse,
    dependencies=[Depends(require_internal)],
)
def state(
    rule_id: UUID,
    body: RuleStateUpdate,
    session: SessionDependency,
    actor: ActorDependency,
    x_actor_managed_project_ids: str | None = Header(default=None),
) -> RuleResponse:
    try:
        return RuleResponse.model_validate(
            update_rule(
                session,
                actor,
                rule_id,
                name=None,
                enabled=body.enabled,
                expected_version=body.expected_version,
                managed_project_ids=ids(x_actor_managed_project_ids),
            )
        )
    except WorkflowError as error:
        raise failure(error) from error


@app.get(
    "/internal/executions", response_model=ExecutionPage, dependencies=[Depends(require_internal)]
)
def executions(
    session: SessionDependency,
    actor: ActorDependency,
    first: int = Query(20, ge=1, le=50),
    after: str | None = None,
    rule_id: UUID | None = None,
    x_actor_project_ids: str | None = Header(default=None),
) -> ExecutionPage:
    page = list_executions(
        session,
        actor,
        project_ids=ids(x_actor_project_ids),
        first=first,
        after=after,
        rule_id=rule_id,
    )
    return ExecutionPage(
        items=[ExecutionResponse.model_validate(item) for item in page.items],
        next_cursor=page.next_cursor,
        has_next_page=page.has_next_page,
    )


@app.get(
    "/internal/executions/{execution_id}",
    response_model=ExecutionResponse,
    dependencies=[Depends(require_internal)],
)
def execution(
    execution_id: UUID,
    session: SessionDependency,
    actor: ActorDependency,
    x_actor_project_ids: str | None = Header(default=None),
) -> ExecutionResponse:
    try:
        return ExecutionResponse.model_validate(
            get_execution(session, actor, execution_id, ids(x_actor_project_ids))
        )
    except WorkflowError as error:
        raise failure(error) from error
