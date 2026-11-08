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
from app.schemas import MarkAllResult, NotificationPage, NotificationResponse, UnreadCount
from app.service import (
    NotificationError,
    list_notifications,
    mark_all_read,
    mark_read,
    unread_count,
)

app = FastAPI(title="Notification Service", docs_url=None, redoc_url=None, openapi_url=None)
SessionDependency = Annotated[Session, Depends(get_session)]


def require_internal(x_internal_service_key: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_internal_service_key, settings.internal_service_key):
        raise HTTPException(403, "Forbidden")


def recipient(x_actor_employee_id: str = Header(default="")) -> UUID:
    try:
        return UUID(x_actor_employee_id)
    except ValueError as error:
        raise HTTPException(403, "Forbidden") from error


Recipient = Annotated[UUID, Depends(recipient)]


def failure(error: NotificationError) -> HTTPException:
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


@app.get(
    "/internal/notifications",
    response_model=NotificationPage,
    dependencies=[Depends(require_internal)],
)
def notifications(
    session: SessionDependency,
    actor: Recipient,
    first: int = Query(20, ge=1, le=50),
    after: str | None = None,
    unread_only: bool = False,
) -> NotificationPage:
    try:
        page = list_notifications(session, actor, first=first, after=after, unread_only=unread_only)
        return NotificationPage(
            items=[NotificationResponse.model_validate(item) for item in page.items],
            next_cursor=page.next_cursor,
            has_next_page=page.has_next_page,
        )
    except NotificationError as error:
        raise failure(error) from error


@app.get(
    "/internal/notifications/unread-count",
    response_model=UnreadCount,
    dependencies=[Depends(require_internal)],
)
def count(session: SessionDependency, actor: Recipient) -> UnreadCount:
    return UnreadCount(count=unread_count(session, actor))


@app.put(
    "/internal/notifications/{notification_id}/read",
    response_model=NotificationResponse,
    dependencies=[Depends(require_internal)],
)
def read(
    notification_id: UUID, session: SessionDependency, actor: Recipient
) -> NotificationResponse:
    try:
        return NotificationResponse.model_validate(mark_read(session, actor, notification_id))
    except NotificationError as error:
        raise failure(error) from error


@app.put(
    "/internal/notifications/read-all",
    response_model=MarkAllResult,
    dependencies=[Depends(require_internal)],
)
def read_all(session: SessionDependency, actor: Recipient) -> MarkAllResult:
    return MarkAllResult(updated_count=mark_all_read(session, actor))
