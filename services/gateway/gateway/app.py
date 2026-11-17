"""Public business API. Current authority is resolved for every GraphQL request."""

import logging
import os
from urllib.parse import urlsplit

import httpx
import strawberry
from fastapi import FastAPI, HTTPException, Request
from graphql import GraphQLError
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


@strawberry.type
class AdminWorkspace:
    viewer: Viewer


@strawberry.type
class ManagedAccount:
    id: strawberry.ID
    display_name: str
    username: str
    email: str
    active: bool
    profile_active: bool
    role: str
    version: int


@strawberry.type
class ProvisioningOperation:
    id: strawberry.ID
    username: str
    email: str
    state: str
    failure_code: str | None


@strawberry.type
class AccountHistory:
    id: strawberry.ID
    actor_id: strawberry.ID
    target_id: strawberry.ID | None
    action: str
    state: str
    before: str
    after: str
    created_at: str


@strawberry.type
class AccountAdministration:
    accounts: list[ManagedAccount]
    operations: list[ProvisioningOperation]
    history: list[AccountHistory]
    has_more: bool


@strawberry.type
class AccountCommandResult:
    operation_id: strawberry.ID
    state: str


@strawberry.input
class CreateAccountInput:
    request_id: strawberry.ID
    username: str
    email: str
    display_name: str
    role: str


@strawberry.input
class ChangeAccountInput:
    request_id: strawberry.ID
    account_id: strawberry.ID
    version: int
    action: str
    role: str | None = None


@strawberry.input
class RecoverAccountInput:
    request_id: strawberry.ID
    operation_id: strawberry.ID


class ActorContext(BaseContext):
    def __init__(self, viewer, load_admin_workspace, administer):
        super().__init__()
        self.viewer = viewer
        self.load_admin_workspace = load_admin_workspace
        self.administer = administer


@strawberry.type
class Query:
    @strawberry.field
    def viewer(self, info: Info[ActorContext, None]) -> Viewer:
        return info.context.viewer

    @strawberry.field
    async def admin_workspace(self, info: Info[ActorContext, None]) -> AdminWorkspace:
        if "admin:workspace:read" not in info.context.viewer.permissions:
            raise GraphQLError("Access denied", extensions={"code": "FORBIDDEN"})
        try:
            viewer = await info.context.load_admin_workspace()
            return AdminWorkspace(viewer=viewer)
        except HTTPException as error:
            code = "FORBIDDEN" if error.status_code in {401, 403} else "SERVICE_UNAVAILABLE"
            raise GraphQLError(
                "Access denied" if code == "FORBIDDEN" else "Service unavailable",
                extensions={"code": code},
            ) from None

    @strawberry.field
    async def account_administration(
        self, info: Info[ActorContext, None], page: int = 0
    ) -> AccountAdministration:
        value = await info.context.administer("list", {"page": page})
        return AccountAdministration(
            accounts=[ManagedAccount(**a) for a in value["accounts"]],
            operations=[ProvisioningOperation(**o) for o in value["operations"]],
            history=[AccountHistory(**h) for h in value["history"]],
            has_more=value["has_more"],
        )


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_account(
        self, info: Info[ActorContext, None], input: CreateAccountInput
    ) -> AccountCommandResult:
        from dataclasses import asdict

        return AccountCommandResult(**await info.context.administer("create", asdict(input)))

    @strawberry.mutation
    async def change_account(
        self, info: Info[ActorContext, None], input: ChangeAccountInput
    ) -> AccountCommandResult:
        from dataclasses import asdict

        return AccountCommandResult(**await info.context.administer("change", asdict(input)))

    @strawberry.mutation
    async def recover_account(
        self, info: Info[ActorContext, None], input: RecoverAccountInput
    ) -> AccountCommandResult:
        from dataclasses import asdict

        return AccountCommandResult(**await info.context.administer("recover", asdict(input)))


class SafeSchema(strawberry.Schema):
    def process_errors(self, errors, execution_context=None):
        logging.getLogger("gateway").warning("graphql_request_rejected")


schema = SafeSchema(
    query=Query, mutation=Mutation, extensions=[lambda: QueryDepthLimiter(max_depth=5)]
)


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

        async def read_actor(path):
            try:
                async with httpx.AsyncClient(
                    timeout=5, transport=transport, follow_redirects=False
                ) as client:
                    response = await client.get(
                        people_url.rstrip("/") + path,
                        headers={
                            "Authorization": authorization,
                            "X-Service-Key": settings.service_key,
                        },
                    )
                if response.status_code in {401, 403}:
                    raise HTTPException(response.status_code, "Access denied")
                response.raise_for_status()
                value = response.json()
                if (
                    set(value)
                    != {
                        "account_id",
                        "employee_id",
                        "display_name",
                        "company_roles",
                        "permissions",
                    }
                    or value["company_roles"] not in [["ADMIN"], ["MANAGER"], ["EMPLOYEE"], ["HR"]]
                    or value["permissions"]
                    != (
                        ["account:self:read", "admin:workspace:read"]
                        if value["company_roles"] == ["ADMIN"]
                        else ["account:self:read"]
                    )
                ):
                    raise ValueError("Invalid actor response")
                return Viewer(**value)
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(503, "Service unavailable") from None

        viewer = await read_actor("/internal/actor")

        async def load_admin_workspace():
            current = await read_actor("/internal/admin/workspace")
            if (
                current.account_id != viewer.account_id
                or current.company_roles != ["ADMIN"]
                or "admin:workspace:read" not in current.permissions
            ):
                raise HTTPException(403, "Access denied")
            return current

        async def administer(command, value):
            if viewer.company_roles != ["ADMIN"]:
                raise GraphQLError("Access denied", extensions={"code": "FORBIDDEN"})
            try:
                async with httpx.AsyncClient(
                    timeout=20, transport=transport, follow_redirects=False
                ) as client:
                    headers = {
                        "Authorization": authorization,
                        "X-Service-Key": settings.service_key,
                    }
                    if command == "list":
                        response = await client.get(
                            people_url.rstrip("/") + "/internal/admin/accounts",
                            params=value,
                            headers=headers,
                        )
                    else:
                        response = await client.post(
                            people_url.rstrip("/") + "/internal/admin/accounts/" + command,
                            json=value,
                            headers=headers,
                        )
                if response.status_code in {401, 403}:
                    raise GraphQLError("Access denied", extensions={"code": "FORBIDDEN"})
                if response.status_code in {400, 404, 409}:
                    allowed = {
                        "invalid_request",
                        "invalid_account_details",
                        "request_conflict",
                        "account_already_requested",
                        "not_found",
                        "already_complete",
                        "invalid_action",
                        "stale_account",
                        "invalid_role",
                        "self_access_change_denied",
                        "last_administrator_required",
                        "inactive_profile",
                        "provisioning_incomplete",
                    }
                    detail = response.json().get("detail")
                    raise GraphQLError(
                        detail if detail in allowed else "Account change rejected",
                        extensions={"code": "ACCOUNT_CHANGE_REJECTED"},
                    )
                response.raise_for_status()
                return response.json()
            except GraphQLError:
                raise
            except Exception:
                raise GraphQLError(
                    "Service unavailable", extensions={"code": "SERVICE_UNAVAILABLE"}
                ) from None

        return ActorContext(viewer, load_admin_workspace, administer)

    app.include_router(
        GraphQLRouter(
            schema,
            context_getter=context,
            graphql_ide=None,
            allow_queries_via_get=False,
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
