"""Private calendar API; identity and current people authority are checked independently."""

import os
from hmac import compare_digest
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException, Request
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from taskspace_security.settings import SecuritySettings
from taskspace_security.tokens import TokenVerifier

from .calendar import CalendarError
from .coordination import CoordinationService
from .memberships import MembershipService
from .owner_decisions import OwnerDecisionService
from .projects import ProjectActor, ProjectError, ProjectService
from .review_fallbacks import ReviewFallbackService
from .service import CalendarService, identifier
from .tasks import TaskService


def create_app(
    settings=None,
    sessions=None,
    verifier=None,
    people_transport=None,
    service_key=None,
    fallback_grant_roles=None,
):
    settings = settings or SecuritySettings.from_environment()
    service_key = service_key or os.environ["PROJECT_WORK_SERVICE_KEY"]
    if len(service_key) < 43:
        raise ValueError("Invalid project-work credential")
    people_url = os.environ.get("PEOPLE_URL", "http://people:8000")
    u = urlsplit(people_url)
    if (
        u.username
        or u.password
        or u.query
        or u.fragment
        or u.path not in {"", "/"}
        or not u.netloc
        or (
            u.scheme != "https"
            and not (
                os.environ.get("AUTH_ALLOW_LOCAL_HTTP") == "true"
                and people_url == "http://people:8000"
            )
        )
    ):
        raise ValueError("Invalid people boundary")
    if sessions is None:
        sessions = sessionmaker(
            create_engine(
                os.environ["PROJECT_WORK_DATABASE_URL"], pool_pre_ping=True, hide_parameters=True
            )
        )
    verifier = verifier or TokenVerifier(
        settings.issuer, settings.jwks_url, settings.audience, settings.client_id
    )
    service = CalendarService(sessions)
    projects = ProjectService(sessions)
    memberships = MembershipService(sessions)
    owner_decisions = OwnerDecisionService(sessions)
    # Confirmed policy: only the current project owner or ADMIN records absence.
    fallbacks = ReviewFallbackService(
        sessions,
        {"ADMIN", "MANAGER"} if fallback_grant_roles is None else fallback_grant_roles,
    )
    coordination = CoordinationService(sessions)
    tasks = TaskService(sessions)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def authority(request, project_access=False):
        key = request.headers.get("x-service-key", "")
        authorization = request.headers.get("authorization", "")
        if (
            not key.isascii()
            or not compare_digest(key, service_key)
            or not authorization.startswith("Bearer ")
        ):
            raise HTTPException(401, "Authentication required")
        try:
            identity = verifier.verify(authorization[7:])
        except Exception:
            raise HTTPException(401, "Authentication required") from None
        if identity.issuer != settings.issuer:
            raise HTTPException(401, "Authentication required")

        def current():
            try:
                with httpx.Client(
                    timeout=5, transport=people_transport, follow_redirects=False
                ) as client:
                    response = client.get(
                        people_url.rstrip("/")
                        + ("/internal/actor" if project_access else "/internal/admin/workspace"),
                        headers={
                            "Authorization": authorization,
                            "X-Service-Key": settings.service_key,
                        },
                    )
                if response.status_code in {401, 403}:
                    raise HTTPException(403, "Access denied")
                response.raise_for_status()
                actor = response.json()
                if project_access:
                    role = actor.get("company_roles")
                    if role not in [["ADMIN"], ["MANAGER"], ["EMPLOYEE"]]:
                        raise HTTPException(403, "Access denied")
                    expected = (
                        ["account:self:read", "admin:workspace:read"]
                        if role == ["ADMIN"]
                        else ["account:self:read"]
                    )
                    if actor.get("permissions") != expected:
                        raise HTTPException(403, "Access denied")
                    name = actor.get("display_name")
                    if not isinstance(name, str) or not 1 <= len(name) <= 150:
                        raise ValueError("Invalid actor")
                    return ProjectActor(
                        identity.issuer, identifier(actor["account_id"]), role[0], name
                    )
                if actor["company_roles"] != ["ADMIN"] or actor["permissions"] != [
                    "account:self:read",
                    "admin:workspace:read",
                ]:
                    raise HTTPException(403, "Access denied")
                return identity.issuer, identifier(actor["account_id"])
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(503, "Authority unavailable") from None

        return current

    @app.get("/internal/admin/calendar")
    def workspace(request: Request):
        try:
            return service.workspace(authority(request))
        except CalendarError as error:
            raise HTTPException(error.status, error.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.post("/internal/admin/calendar/{command}")
    def command(command: str, value: dict, request: Request):
        try:
            actor = authority(request)
            actor()
            if command == "preview":
                return service.preview(actor, value)
            if command == "publish":
                return service.publish(actor, value)
            if command == "calculate":
                return service.calculation(actor, value)
            raise HTTPException(404, "Not found")
        except CalendarError as error:
            raise HTTPException(error.status, error.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.get("/internal/projects")
    def project_workspace(request: Request, page: int = 0, search: str = ""):
        try:
            return projects.workspace(authority(request, True), page, search)
        except ProjectError as error:
            raise HTTPException(error.status, error.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.get("/internal/projects/{project_id}")
    def project_detail(project_id: str, request: Request):
        try:
            return projects.detail(authority(request, True), project_id)
        except ProjectError as error:
            raise HTTPException(error.status, error.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.post("/internal/projects/{command}")
    def project_command(command: str, value: dict, request: Request):
        try:
            actor = authority(request, True)
            actor()
            if command == "preview":
                return projects.preview(actor, value)
            if command == "create":
                return projects.create(actor, value)
            raise HTTPException(404, "Not found")
        except ProjectError as error:
            raise HTTPException(error.status, error.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    def directory(request, **params):
        # Reached only after project ownership authorization in MembershipService.
        try:
            with httpx.Client(
                timeout=5, transport=people_transport, follow_redirects=False
            ) as client:
                response = client.get(
                    people_url.rstrip("/") + "/internal/project-candidates",
                    params=params,
                    headers={
                        "Authorization": request.headers.get("authorization", ""),
                        "X-Service-Key": settings.service_key,
                    },
                )
            if response.status_code in {401, 403}:
                raise HTTPException(403, "Access denied")
            response.raise_for_status()
            return response.json()
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Authority unavailable") from None

    @app.get("/internal/project-memberships/{project_id}")
    def membership_workspace(project_id: str, request: Request):
        try:
            return memberships.workspace(authority(request, True), project_id)
        except ProjectError as error:
            raise HTTPException(error.status, error.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.get("/internal/project-memberships/{project_id}/candidates")
    def membership_candidates(project_id: str, request: Request, page: int = 0, search: str = ""):
        try:
            return memberships.candidates(
                authority(request, True),
                project_id,
                lambda p, q: directory(request, page=p, search=q),
                page,
                search,
            )
        except ProjectError as error:
            raise HTTPException(error.status, error.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.post("/internal/project-memberships/change")
    def membership_change(value: dict, request: Request):
        try:
            return memberships.change(
                authority(request, True),
                lambda account_id: directory(request, account_id=account_id),
                value,
            )
        except ProjectError as error:
            raise HTTPException(error.status, error.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.get("/internal/project-coordination/{project_id}")
    def coordination_workspace(project_id: str, request: Request, page: int = 0):
        try:
            return coordination.workspace(authority(request, True), project_id, page)
        except ProjectError as error:
            raise HTTPException(error.status, error.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.post("/internal/project-coordination/{command}")
    def coordination_command(command: str, value: dict, request: Request):
        try:
            actor = authority(request, True)
            if command == "create":
                return coordination.create(
                    actor, lambda target: directory(request, account_id=target), value
                )
            if command == "follow-up":
                return coordination.follow_up(actor, value)
            raise HTTPException(404, "Not found")
        except ProjectError as error:
            raise HTTPException(error.status, error.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.get("/internal/project-oversight/{project_id}")
    def owner_workspace(project_id: str, request: Request, page: int = 0):
        try:
            return owner_decisions.workspace(authority(request, True), project_id, page)
        except ProjectError as error:
            raise HTTPException(error.status, error.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.get("/internal/project-oversight/{project_id}/fallbacks")
    def owner_fallbacks(project_id: str, request: Request, page: int = 0):
        try:
            return fallbacks.workspace(authority(request, True), project_id, page)
        except ProjectError as error:
            raise HTTPException(error.status, error.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.post("/internal/project-oversight/{command}")
    def owner_command(command: str, value: dict, request: Request):
        try:
            actor = authority(request, True)
            if command == "preview":
                return owner_decisions.preview(actor, value)
            if command == "decide":
                return owner_decisions.decide(actor, value)
            if command == "fallback-create":
                return fallbacks.create(actor, value)
            if command == "fallback-revoke":
                return fallbacks.revoke(actor, value)
            raise HTTPException(404, "Not found")
        except ProjectError as error:
            raise HTTPException(error.status, error.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    def task_directory(request, ids):
        try:
            with httpx.Client(
                timeout=5, transport=people_transport, follow_redirects=False
            ) as client:
                response = client.post(
                    people_url.rstrip("/") + "/internal/task-references",
                    json={"account_ids": ids},
                    headers={
                        "Authorization": request.headers.get("authorization", ""),
                        "X-Service-Key": settings.service_key,
                    },
                )
            if response.status_code in {401, 403}:
                raise HTTPException(403, "Access denied")
            response.raise_for_status()
            return response.json()
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Authority unavailable") from None

    @app.get("/internal/project-tasks/{project_id}")
    def task_workspace(project_id: str, request: Request, page: int = 0):
        try:
            return tasks.workspace(authority(request, True), project_id, page)
        except ProjectError as error:
            raise HTTPException(error.status, error.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.get("/internal/project-tasks/{project_id}/candidates")
    def task_candidates(project_id: str, request: Request, page: int = 0):
        try:
            return tasks.candidates(
                authority(request, True), project_id, lambda ids: task_directory(request, ids), page
            )
        except ProjectError as error:
            raise HTTPException(error.status, error.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.post("/internal/project-tasks/change")
    def task_change(request: Request, value: dict):
        try:
            return tasks.change(
                authority(request, True), lambda ids: task_directory(request, ids), value
            )
        except ProjectError as error:
            raise HTTPException(error.status, error.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.get("/health/live")
    def live():
        return {"status": "up"}

    @app.get("/health/ready")
    def ready():
        try:
            with sessions() as s:
                s.execute(text("SELECT 1 FROM calendar_versions LIMIT 1"))
                s.execute(text("SELECT 1 FROM projects LIMIT 1"))
                s.execute(text("SELECT 1 FROM project_membership_changes LIMIT 1"))
                s.execute(text("SELECT 1 FROM coordination_records LIMIT 1"))
                s.execute(text("SELECT 1 FROM project_owner_decisions LIMIT 1"))
                s.execute(text("SELECT 1 FROM work_tasks LIMIT 1"))
            return {"status": "up"}
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.middleware("http")
    async def privacy(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return app
