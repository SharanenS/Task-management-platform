import json
import logging
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from strawberry.fastapi import GraphQLRouter
from strawberry.http import GraphQLHTTPResponse
from strawberry.types import ExecutionResult

from app.config import settings
from app.schema import schema


class SafeGraphQLRouter(GraphQLRouter):
    async def process_result(
        self, request: Request, result: ExecutionResult
    ) -> GraphQLHTTPResponse:
        response = await super().process_result(request, result)
        if result.errors:
            response["errors"] = [
                {
                    "message": "Request could not be completed."
                    if error.original_error
                    else "Invalid GraphQL request."
                }
                for error in result.errors
            ]
        return response


app = FastAPI(
    title="Enterprise Task Platform Gateway", docs_url=None, redoc_url=None, openapi_url=None
)
logger = logging.getLogger("gateway")
logging.basicConfig(level=settings.log_level, format="%(message)s")


@app.middleware("http")
async def request_metadata(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = str(uuid4())
    started = time.monotonic()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    logger.info(
        json.dumps(
            {
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
            }
        )
    )
    return response


@app.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness() -> dict[str, str]:
    # Phase 1 has no database, broker, or other readiness dependencies.
    return {"status": "ready"}


app.include_router(
    SafeGraphQLRouter(
        schema,
        graphql_ide="graphiql" if settings.app_env == "development" else None,
        allow_queries_via_get=False,
    ),
    prefix="/graphql",
)
