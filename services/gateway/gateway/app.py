"""Public business API. Current authority is resolved for every GraphQL request."""

import logging
import os
from urllib.parse import urlsplit
from uuid import UUID

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

from .calendar_schema import CalendarMutation, CalendarQuery
from .organization_schema import OrganizationMutation, OrganizationQuery
from .owner_schema import OwnerMutation, OwnerQuery
from .project_schema import ProjectMutation, ProjectQuery


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
    employee_id: strawberry.ID | None = None


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
    def __init__(self, viewer, load_admin_workspace, administer, organization, calendar, projects):
        super().__init__()
        self.viewer = viewer
        self.load_admin_workspace = load_admin_workspace
        self.administer = administer
        self.organization = organization
        self.calendar = calendar
        self.projects = projects


@strawberry.type
class Query(OrganizationQuery, CalendarQuery, ProjectQuery, OwnerQuery):
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
class Mutation(OrganizationMutation, CalendarMutation, ProjectMutation, OwnerMutation):
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

        async def administer(command, value, domain="accounts"):
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
                            people_url.rstrip("/") + "/internal/admin/" + domain,
                            params=value,
                            headers=headers,
                        )
                    else:
                        response = await client.post(
                            people_url.rstrip("/")
                            + "/internal/admin/"
                            + domain
                            + ("/" + command if domain == "accounts" else ""),
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
                        "invalid_employee_association",
                        "employee_provisioning_pending",
                        "invalid_name",
                        "employee_not_found",
                        "inactive_or_invalid_structure",
                        "reporting_cycle",
                        "inactive_manager",
                        "invalid_structure_kind",
                        "structure_not_found",
                        "duplicate_structure_name",
                        "stale_structure",
                        "invalid_active_status",
                        "structure_in_use",
                        "stale_employee",
                        "invalid_account_association",
                        "employee_already_linked",
                        "identity_not_active",
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

        async def organization(command, value):
            return await administer(command, value, "organization")

        async def calendar(command, value):
            if viewer.company_roles != ["ADMIN"]:
                raise GraphQLError("Access denied", extensions={"code": "FORBIDDEN"})
            origin = os.environ.get("PROJECT_WORK_URL", "http://project-work:8000")
            boundary = urlsplit(origin)
            local = os.environ.get("AUTH_ALLOW_LOCAL_HTTP") == "true"
            if (
                boundary.username
                or boundary.password
                or boundary.query
                or boundary.fragment
                or boundary.path not in {"", "/"}
                or not boundary.netloc
                or (
                    boundary.scheme != "https"
                    and not (local and origin == "http://project-work:8000")
                )
            ):
                raise GraphQLError(
                    "Service unavailable", extensions={"code": "SERVICE_UNAVAILABLE"}
                )
            try:
                key = os.environ["PROJECT_WORK_SERVICE_KEY"]
                if len(key) < 43:
                    raise ValueError()
                async with httpx.AsyncClient(
                    timeout=20, transport=transport, follow_redirects=False
                ) as client:
                    headers = {"Authorization": authorization, "X-Service-Key": key}
                    if command == "workspace":
                        response = await client.get(
                            origin.rstrip("/") + "/internal/admin/calendar", headers=headers
                        )
                    else:
                        response = await client.post(
                            origin.rstrip("/") + "/internal/admin/calendar/" + command,
                            json=value,
                            headers=headers,
                        )
                if response.status_code in {401, 403}:
                    raise GraphQLError("Access denied", extensions={"code": "FORBIDDEN"})
                if response.status_code in {400, 404, 409, 422}:
                    reasons = {
                        "invalid_calendar",
                        "invalid_timezone",
                        "invalid_week",
                        "invalid_working_hours",
                        "non_working_hours",
                        "invalid_working_status",
                        "no_regular_working_day",
                        "invalid_special_dates",
                        "invalid_date",
                        "invalid_label",
                        "duplicate_special_date",
                        "invalid_duration",
                        "ambiguous_or_nonexistent_time",
                        "unsupported_schedule_window",
                        "unsupported_timezone_version",
                        "preview_expired",
                        "stale_calendar_preview",
                        "preview_not_owned",
                        "preview_already_published",
                        "request_conflict",
                        "confirmation_required",
                        "no_calendar_changes",
                        "calendar_version_not_found",
                        "invalid_identifier",
                        "invalid_calendar_preview",
                    }
                    reason = response.json().get("detail")
                    raise GraphQLError(
                        "Calendar change or calculation rejected",
                        extensions={
                            "code": "CALENDAR_REJECTED",
                            "reason": reason
                            if isinstance(reason, str) and reason in reasons
                            else "calendar_rejected",
                        },
                    )
                response.raise_for_status()
                return response.json()
            except GraphQLError:
                raise
            except Exception:
                raise GraphQLError(
                    "Service unavailable", extensions={"code": "SERVICE_UNAVAILABLE"}
                ) from None

        async def projects(command, value):
            if viewer.company_roles not in [["ADMIN"], ["MANAGER"], ["EMPLOYEE"]] or (
                command
                in {
                    "preview",
                    "create",
                    "candidates",
                    "membership-change",
                    "coordination",
                    "coordination-create",
                    "coordination-follow-up",
                    "owner-workspace",
                    "owner-fallbacks",
                    "owner-preview",
                    "owner-decide",
                    "owner-fallback-create",
                    "owner-fallback-revoke",
                }
                and viewer.company_roles not in [["ADMIN"], ["MANAGER"]]
            ):
                raise GraphQLError("Access denied", extensions={"code": "FORBIDDEN"})
            origin = os.environ.get("PROJECT_WORK_URL", "http://project-work:8000")
            boundary = urlsplit(origin)
            local = os.environ.get("AUTH_ALLOW_LOCAL_HTTP") == "true"
            if (
                boundary.username
                or boundary.password
                or boundary.query
                or boundary.fragment
                or boundary.path not in {"", "/"}
                or not boundary.netloc
                or (
                    boundary.scheme != "https"
                    and not (local and origin == "http://project-work:8000")
                )
            ):
                raise GraphQLError(
                    "Service unavailable", extensions={"code": "SERVICE_UNAVAILABLE"}
                )
            try:
                key = os.environ["PROJECT_WORK_SERVICE_KEY"]
                if len(key) < 43:
                    raise ValueError()
                path = origin.rstrip("/") + "/internal/projects"
                async with httpx.AsyncClient(
                    timeout=20, transport=transport, follow_redirects=False
                ) as client:
                    headers = {"Authorization": authorization, "X-Service-Key": key}
                    if command == "list":
                        response = await client.get(path, params=value, headers=headers)
                    elif command in {
                        "detail",
                        "members",
                        "candidates",
                        "coordination",
                        "owner-workspace",
                        "owner-fallbacks",
                    }:
                        try:
                            project_id = str(UUID(value["id"]))
                        except (ValueError, TypeError, AttributeError):
                            raise GraphQLError(
                                "Project unavailable",
                                extensions={
                                    "code": "PROJECT_REJECTED",
                                    "reason": "project_not_found",
                                },
                            ) from None
                        if command in {"owner-workspace", "owner-fallbacks"}:
                            response = await client.get(
                                origin.rstrip("/")
                                + "/internal/project-oversight/"
                                + project_id
                                + ("/fallbacks" if command == "owner-fallbacks" else ""),
                                params={"page": value.get("page", 0)},
                                headers=headers,
                            )
                        elif command == "coordination":
                            response = await client.get(
                                origin.rstrip("/") + "/internal/project-coordination/" + project_id,
                                params={"page": value.get("page", 0)},
                                headers=headers,
                            )
                        elif command == "detail":
                            response = await client.get(path + "/" + project_id, headers=headers)
                        else:
                            membership_path = (
                                origin.rstrip("/") + "/internal/project-memberships/" + project_id
                            )
                            if command == "candidates":
                                membership_path += "/candidates"
                            response = await client.get(
                                membership_path,
                                params={k: v for k, v in value.items() if k != "id"},
                                headers=headers,
                            )
                    elif command in {
                        "owner-preview",
                        "owner-decide",
                        "owner-fallback-create",
                        "owner-fallback-revoke",
                    }:
                        response = await client.post(
                            origin.rstrip("/")
                            + "/internal/project-oversight/"
                            + command.removeprefix("owner-"),
                            json=value,
                            headers=headers,
                        )
                    elif command in {"coordination-create", "coordination-follow-up"}:
                        response = await client.post(
                            origin.rstrip("/")
                            + "/internal/project-coordination/"
                            + command.removeprefix("coordination-"),
                            json=value,
                            headers=headers,
                        )
                    elif command == "membership-change":
                        response = await client.post(
                            origin.rstrip("/") + "/internal/project-memberships/change",
                            json=value,
                            headers=headers,
                        )
                    else:
                        response = await client.post(
                            path + "/" + command, json=value, headers=headers
                        )
                if response.status_code in {401, 403}:
                    raise GraphQLError("Access denied", extensions={"code": "FORBIDDEN"})
                if response.status_code in {400, 404, 409, 422}:
                    reasons = {
                        "invalid_owner_request",
                        "stale_owner_escalation",
                        "owner_escalation_not_found",
                        "owner_assessment_required",
                        "owner_escalation_within_deadline",
                        "owner_calendar_required",
                        "owner_deadline_before_forecast",
                        "stale_owner_preview",
                        "owner_request_conflict",
                        "invalid_fallback_record",
                        "invalid_fallback_period",
                        "stale_fallback_leader",
                        "fallback_not_found",
                        "fallback_already_revoked",
                        "invalid_coordination",
                        "invalid_coordination_time",
                        "coordination_request_conflict",
                        "coordination_recipient_ineligible",
                        "coordination_not_found",
                        "coordination_stale",
                        "coordination_follow_up_limit",
                        "invalid_membership_change",
                        "stale_project_membership",
                        "member_not_eligible",
                        "membership_not_active",
                        "leader_already_appointed",
                        "project_membership_limit",
                        "no_membership_change",
                        "project_not_found",
                        "invalid_project_details",
                        "invalid_identifier",
                        "invalid_page",
                        "company_calendar_required",
                        "unsupported_timezone_version",
                        "invalid_date",
                        "invalid_working_hours",
                        "ambiguous_or_nonexistent_time",
                        "non_working_deadline",
                        "invalid_project_deadline",
                        "confirmation_required",
                        "preview_not_owned",
                        "preview_expired",
                        "stale_project_calendar",
                        "preview_already_used",
                        "request_conflict",
                    }
                    reason = response.json().get("detail")
                    raise GraphQLError(
                        "Project request rejected",
                        extensions={
                            "code": "PROJECT_REJECTED",
                            "reason": reason
                            if isinstance(reason, str) and reason in reasons
                            else "project_rejected",
                        },
                    )
                response.raise_for_status()
                return response.json()
            except GraphQLError:
                raise
            except Exception:
                raise GraphQLError(
                    "Service unavailable", extensions={"code": "SERVICE_UNAVAILABLE"}
                ) from None

        return ActorContext(
            viewer, load_admin_workspace, administer, organization, calendar, projects
        )

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
