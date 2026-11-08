import hmac
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request, Response
from strawberry.fastapi import GraphQLRouter
from strawberry.http import GraphQLHTTPResponse
from strawberry.types import ExecutionResult

from app.config import settings
from app.observability import (
    categorize_graphql_operation,
    correlation_id_ctx,
    format_traceparent,
    metrics,
    parse_traceparent,
    telemetry,
    validate_correlation_id,
)
from app.schema import schema


class SafeGraphQLRouter(GraphQLRouter):
    async def execute_operation(
        self,
        request: Request,
        request_adapter: Any,
        request_data: Any,
        context: Any,
        root_value: Any,
        sub_response: Any,
    ) -> Any:
        query_str = None
        op_name = None
        if isinstance(request_data, list) and request_data:
            query_str = getattr(request_data[0], "query", None)
            op_name = getattr(request_data[0], "operation_name", None)
        elif hasattr(request_data, "query"):
            query_str = getattr(request_data, "query", None)
            op_name = getattr(request_data, "operation_name", None)

        op_type, op_cat = categorize_graphql_operation(query_str, op_name)
        metrics.counter(
            "graphql_operations_total",
            labels={"operation_type": op_type, "operation_name": op_cat},
            help_text="Total number of GraphQL operations processed",
        )
        return await super().execute_operation(
            request, request_adapter, request_data, context, root_value, sub_response
        )

    async def process_result(
        self, request: Request, result: ExecutionResult
    ) -> GraphQLHTTPResponse:
        response = await super().process_result(request, result)
        if result.errors:
            safe_errors: list[object] = []
            for error in result.errors:
                code = error.extensions.get("code") if error.extensions else None
                if error.message and "exceeds maximum operation depth" in error.message:
                    safe_errors.append(
                        {
                            "message": error.message,
                            "extensions": {"code": "QUERY_TOO_COMPLEX"},
                        }
                    )
                elif code == "MEMBER_HAS_ASSIGNED_TASKS":
                    safe_errors.append(
                        {
                            "message": (
                                "Reassign the employee's tasks before removing project membership."
                            ),
                            "extensions": {"code": "MEMBER_HAS_ASSIGNED_TASKS"},
                        }
                    )
                elif code in {
                    "UNAUTHENTICATED",
                    "FORBIDDEN",
                    "SERVICE_UNAVAILABLE",
                    "INVALID_INPUT",
                    "NOT_FOUND",
                    "DUPLICATE_EMPLOYEE",
                    "IDENTITY_COLLISION",
                    "IDEMPOTENCY_CONFLICT",
                    "SELF_PROTECTED",
                    "FINAL_ADMIN",
                    "RECONCILIATION_REQUIRED",
                    "INVALID_CURSOR",
                    "INVALID_PAGE_SIZE",
                    "JOB_NOT_FOUND",
                    "JOB_NOT_DISPATCHABLE",
                    "JOB_NOT_RETRYABLE",
                    "JOB_RETRY_CONFLICT",
                    "BROKER_UNAVAILABLE",
                    "ARTIFACT_UNAVAILABLE",
                    "PROJECT_KEY_CONFLICT",
                    "MEMBERSHIP_CONFLICT",
                    "VERSION_CONFLICT",
                    "INVALID_STATUS",
                    "PROJECT_ARCHIVED",
                    "FINAL_PROJECT_MANAGER",
                    "EMPLOYEE_NOT_ELIGIBLE",
                    "QUERY_TOO_COMPLEX",
                }:
                    safe_errors.append({"message": error.message, "extensions": {"code": code}})
                else:
                    safe_errors.append(
                        {
                            "message": "Request could not be completed."
                            if error.original_error
                            else "Invalid GraphQL request."
                        }
                    )
            response["errors"] = safe_errors
        return response


app = FastAPI(
    title="Enterprise Task Platform Gateway", docs_url=None, redoc_url=None, openapi_url=None
)
logger = logging.getLogger("gateway")
logging.basicConfig(level=settings.log_level, format="%(message)s")


async def graphql_context(request: Request) -> dict[str, str | None]:
    return {"authorization": request.headers.get("authorization")}


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
    if path == "/graphql":
        path_label = "/graphql"
    elif path.startswith("/health/"):
        path_label = path
    elif path == "/metrics":
        path_label = "/metrics"
    else:
        path_label = "other"

    span = telemetry.start_span(
        "http_request",
        parent_trace_id=parent_trace_id,
        parent_span_id=parent_span_id,
        attributes={
            "http.method": request.method,
            "http.route": path_label,
        },
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
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness() -> dict[str, str]:
    # Phase 1 has no database, broker, or other readiness dependencies.
    return {"status": "ready"}


@app.get("/metrics")
async def prometheus_metrics(
    authorization: str = Header(default=""),
    x_metrics_token: str = Header(default="", alias="X-Metrics-Token"),
) -> Response:
    token = ""
    if authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif x_metrics_token:
        token = x_metrics_token.strip()

    expected = settings.gateway_metrics_token.strip()
    if not expected or not token or not hmac.compare_digest(token, expected):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized metrics access",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Response(
        content=metrics.render_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


app.include_router(
    SafeGraphQLRouter(
        schema,
        context_getter=graphql_context,
        graphql_ide="graphiql" if settings.app_env == "development" else None,
        allow_queries_via_get=False,
    ),
    prefix="/graphql",
)
