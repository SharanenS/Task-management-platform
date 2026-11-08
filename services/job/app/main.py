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
from app.models import JobStatus, JobType, PublicationStatus
from app.observability import (
    correlation_id_ctx,
    format_traceparent,
    metrics,
    parse_traceparent,
    telemetry,
    validate_correlation_id,
)
from app.schemas import (
    JobAttemptPageResponse,
    JobAttemptResponse,
    JobDashboardResponse,
    JobDispatchRequest,
    JobOperationsSummaryResponse,
    JobPageResponse,
    JobResponse,
    JobRetryRequest,
    JobSubmissionRequest,
    PublicationPageResponse,
    PublicationResponse,
)
from app.service import (
    Actor,
    JobError,
    admin_retry_job,
    dispatch_job,
    get_dashboard_metrics,
    get_job,
    get_operations_summary,
    list_attempts,
    list_jobs,
    list_publications,
    submit_job,
)

app = FastAPI(title="Job Service", docs_url=None, redoc_url=None, openapi_url=None)
SessionDependency = Annotated[Session, Depends(get_session)]


def require_internal_service(x_internal_service_key: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_internal_service_key, settings.internal_service_key):
        raise HTTPException(status_code=403, detail="Forbidden")


def require_workflow_service(x_workflow_service_key: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_workflow_service_key, settings.workflow_service_key):
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


def failure(error: JobError) -> HTTPException:
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
    response_model=JobOperationsSummaryResponse,
    dependencies=[Depends(require_internal_service)],
)
def operations_summary(session: SessionDependency) -> JobOperationsSummaryResponse:
    return get_operations_summary(session)


@app.get(
    "/internal/dashboard/metrics",
    response_model=JobDashboardResponse,
    dependencies=[Depends(require_internal_service)],
)
def dashboard_metrics(session: SessionDependency, actor: ActorDependency) -> JobDashboardResponse:
    try:
        return get_dashboard_metrics(session, actor)
    except JobError as error:
        raise failure(error) from error


@app.get(
    "/internal/jobs",
    response_model=JobPageResponse,
    dependencies=[Depends(require_internal_service)],
)
def directory(
    session: SessionDependency,
    actor: ActorDependency,
    first: int = Query(default=20, ge=1, le=50),
    after: str | None = None,
    status: JobStatus | None = None,
    job_type: JobType | None = None,
) -> JobPageResponse:
    try:
        page = list_jobs(session, actor, first=first, after=after, status=status, job_type=job_type)
        return JobPageResponse(
            items=[JobResponse.model_validate(item) for item in page.items],
            next_cursor=page.next_cursor,
            has_next_page=page.has_next_page,
        )
    except JobError as error:
        raise failure(error) from error


@app.get(
    "/internal/publications",
    response_model=PublicationPageResponse,
    dependencies=[Depends(require_internal_service)],
)
def publications(
    session: SessionDependency,
    actor: ActorDependency,
    first: int = Query(default=20, ge=1, le=50),
    after: str | None = None,
    status: PublicationStatus | None = None,
) -> PublicationPageResponse:
    try:
        page = list_publications(session, actor, first=first, after=after, status=status)
        return PublicationPageResponse(
            items=[PublicationResponse.model_validate(item) for item in page.items],
            next_cursor=page.next_cursor,
            has_next_page=page.has_next_page,
        )
    except JobError as error:
        raise failure(error) from error


@app.get(
    "/internal/jobs/{job_id}",
    response_model=JobResponse,
    dependencies=[Depends(require_internal_service)],
)
def detail(job_id: UUID, session: SessionDependency, actor: ActorDependency) -> JobResponse:
    try:
        return JobResponse.model_validate(get_job(session, actor, job_id))
    except JobError as error:
        raise failure(error) from error


@app.get(
    "/internal/jobs/{job_id}/attempts",
    response_model=JobAttemptPageResponse,
    dependencies=[Depends(require_internal_service)],
)
def attempts(
    job_id: UUID, session: SessionDependency, actor: ActorDependency
) -> JobAttemptPageResponse:
    try:
        return JobAttemptPageResponse(
            items=[
                JobAttemptResponse.model_validate(item)
                for item in list_attempts(session, actor, job_id)
            ]
        )
    except JobError as error:
        raise failure(error) from error


@app.post(
    "/internal/jobs", response_model=JobResponse, dependencies=[Depends(require_internal_service)]
)
def submit(
    body: JobSubmissionRequest, session: SessionDependency, actor: ActorDependency
) -> JobResponse:
    try:
        return JobResponse.model_validate(submit_job(session, actor, body))
    except JobError as error:
        raise failure(error) from error


@app.post(
    "/internal/workflow/jobs",
    response_model=JobResponse,
    dependencies=[Depends(require_workflow_service)],
)
def submit_workflow_job(
    body: JobSubmissionRequest,
    session: SessionDependency,
    x_workflow_actor_employee_id: str = Header(default=""),
) -> JobResponse:
    try:
        actor = Actor(UUID(x_workflow_actor_employee_id), "MEMBER")
        job = submit_job(session, actor, body)
        if job.status.value == "SUBMITTED":
            job = dispatch_job(session, actor, job.id, job.version)
        return JobResponse.model_validate(job)
    except ValueError as error:
        raise HTTPException(status_code=403, detail="Forbidden") from error
    except JobError as error:
        raise failure(error) from error


@app.post(
    "/internal/jobs/{job_id}/dispatch",
    response_model=JobResponse,
    dependencies=[Depends(require_internal_service)],
)
def dispatch(
    job_id: UUID,
    body: JobDispatchRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> JobResponse:
    try:
        return JobResponse.model_validate(
            dispatch_job(session, actor, job_id, body.expected_version)
        )
    except JobError as error:
        raise failure(error) from error


@app.post(
    "/internal/jobs/{job_id}/retry",
    response_model=JobResponse,
    dependencies=[Depends(require_internal_service)],
)
def retry(
    job_id: UUID,
    body: JobRetryRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> JobResponse:
    try:
        return JobResponse.model_validate(
            admin_retry_job(session, actor, job_id, body.expected_version)
        )
    except JobError as error:
        raise failure(error) from error
