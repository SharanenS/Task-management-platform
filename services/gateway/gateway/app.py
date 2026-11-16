"""Public business API. Current authority is resolved for every GraphQL request."""

import logging
import os
from urllib.parse import urlsplit

import httpx
import strawberry
from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from strawberry.extensions import QueryDepthLimiter
from strawberry.fastapi import BaseContext, GraphQLRouter
from strawberry.types import Info
from taskspace_security.settings import SecuritySettings
from taskspace_security.tokens import TokenVerifier


@strawberry.type
class Viewer:
    account_id: strawberry.ID
    employee_id: strawberry.ID
    display_name: str
    company_roles: list[str]
    permissions: list[str]


class ActorContext(BaseContext):
    def __init__(self, viewer):
        super().__init__()
        self.viewer = viewer


@strawberry.type
class Query:
    @strawberry.field
    def viewer(self, info: Info[ActorContext, None]) -> Viewer:
        return info.context.viewer


class SafeSchema(strawberry.Schema):
    def process_errors(self, errors, execution_context=None):
        logging.getLogger("gateway").warning("graphql_request_rejected")


schema = SafeSchema(query=Query, extensions=[lambda: QueryDepthLimiter(max_depth=5)])


def create_app(settings=None, verifier=None, transport=None):
    settings = settings or SecuritySettings.from_environment()
    verifier = verifier or TokenVerifier(
        settings.issuer, settings.jwks_url, settings.audience, settings.client_id
    )
    people_url = os.environ.get("PEOPLE_URL", "http://people:8000")
    parsed = urlsplit(people_url)
    if (
        parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or (
            parsed.scheme != "https"
            and not (
                os.environ.get("AUTH_ALLOW_LOCAL_HTTP") == "true"
                and people_url == "http://people:8000"
            )
        )
    ):
        raise ValueError("Invalid people service boundary")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    async def context(request: Request):
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "Authentication required")
        try:
            await run_in_threadpool(verifier.verify, authorization[7:])
        except Exception:
            raise HTTPException(401, "Authentication required") from None
        try:
            async with httpx.AsyncClient(
                timeout=5, transport=transport, follow_redirects=False
            ) as client:
                response = await client.get(
                    people_url.rstrip("/") + "/internal/actor",
                    headers={"Authorization": authorization, "X-Service-Key": settings.service_key},
                )
            if response.status_code in {401, 403}:
                raise HTTPException(response.status_code, "Access denied")
            response.raise_for_status()
            value = response.json()
            if set(value) != {
                "account_id",
                "employee_id",
                "display_name",
                "company_roles",
                "permissions",
            } or value["permissions"] != ["account:self:read"]:
                raise ValueError("Invalid actor response")
            return ActorContext(Viewer(**value))
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    app.include_router(
        GraphQLRouter(
            schema, context_getter=context, graphql_ide=None, allow_queries_via_get=False
        ),
        prefix="/graphql",
    )

    @app.get("/health/live")
    def live():
        return {"status": "up"}

    @app.middleware("http")
    async def private_responses(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return app
