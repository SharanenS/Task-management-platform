"""Private people API: authenticate the gateway and independently verify its bearer."""

import os
from dataclasses import asdict
from hmac import compare_digest

from fastapi import FastAPI, HTTPException, Request
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from taskspace_security.settings import SecuritySettings
from taskspace_security.tokens import TokenVerifier

from .access import AccessDenied, resolve_actor
from .identity_admin import IdentityAdministration
from .management import AccountManagement, ManagementError
from .organization import OrganizationManagement
from .project_directory import ProjectDirectory


def create_app(settings=None, sessions=None, verifier=None, provider=None):
    settings = settings or SecuritySettings.from_environment()
    if sessions is None:
        engine = create_engine(
            os.environ["PEOPLE_DATABASE_URL"], pool_pre_ping=True, hide_parameters=True
        )
        sessions = sessionmaker(engine)
    verifier = verifier or TokenVerifier(
        settings.issuer, settings.jwks_url, settings.audience, settings.client_id
    )
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    management = AccountManagement(sessions, provider or (lambda: IdentityAdministration(settings)))

    organization = OrganizationManagement(
        sessions, provider or (lambda: IdentityAdministration(settings))
    )

    @app.get("/health/live")
    def live():
        return {"status": "up"}

    @app.get("/health/ready")
    def ready():
        try:
            with sessions() as session:
                session.execute(text("SELECT 1 FROM accounts LIMIT 1"))
            return {"status": "up"}
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    def current_identity(request: Request):
        service_key = request.headers.get("x-service-key", "")
        if not service_key.isascii() or not compare_digest(service_key, settings.service_key):
            raise HTTPException(401, "Authentication required")
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "Authentication required")
        try:
            return verifier.verify(authorization[7:])
        except Exception:
            raise HTTPException(401, "Authentication required") from None

    def current_actor(request: Request):
        identity = current_identity(request)
        try:
            with sessions() as session:
                value = resolve_actor(session, identity)
                return value
        except AccessDenied:
            raise HTTPException(403, "Access denied") from None
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.get("/internal/actor")
    def actor(request: Request):
        return asdict(current_actor(request))

    @app.get("/internal/project-candidates")
    def project_candidates(
        request: Request, page: int = 0, search: str = "", account_id: str | None = None
    ):
        try:
            return ProjectDirectory(sessions).lookup(
                current_identity(request), account_id, page, search
            )
        except AccessDenied:
            raise HTTPException(403, "Access denied") from None
        except (ValueError, TypeError):
            raise HTTPException(400, "Invalid candidate request") from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Authority unavailable") from None

    @app.post("/internal/task-references")
    def task_references(request: Request, value: dict):
        try:
            if set(value) != {"account_ids"}:
                raise ValueError("Invalid account references")
            return ProjectDirectory(sessions).task_references(
                current_identity(request), value["account_ids"]
            )
        except AccessDenied:
            raise HTTPException(403, "Access denied") from None
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(400, "Invalid account references") from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Authority unavailable") from None

    @app.get("/internal/admin/workspace")
    def admin_workspace(request: Request):
        actor = current_actor(request)
        if actor.company_roles != ("ADMIN",) or "admin:workspace:read" not in actor.permissions:
            raise HTTPException(403, "Access denied")
        return asdict(actor)

    @app.get("/internal/admin/accounts")
    def accounts(request: Request, page: int = 0):
        try:
            return management.list(current_identity(request), page)
        except AccessDenied:
            raise HTTPException(403, "Access denied") from None
        except ManagementError as error:
            raise HTTPException(error.status, error.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.post("/internal/admin/accounts/{command}")
    def account_command(command: str, value: dict, request: Request):
        identity = current_identity(request)
        try:
            if command == "create":
                return management.create(identity, value)
            if command == "recover":
                return management.recover(identity, value)
            if command == "change":
                return management.change(identity, value)
            raise HTTPException(404, "Not found")
        except AccessDenied:
            raise HTTPException(403, "Access denied") from None
        except ManagementError as error:
            raise HTTPException(error.status, error.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.get("/internal/admin/organization")
    def organization_workspace(request: Request, page: int = 0, search: str = ""):
        identity = current_identity(request)
        try:
            return organization.workspace(identity, page, search)
        except AccessDenied:
            raise HTTPException(403, "Access denied") from None
        except ManagementError as error:
            raise HTTPException(error.status, error.code) from None
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.post("/internal/admin/organization")
    def organization_change(value: dict, request: Request):
        identity = current_identity(request)
        try:
            return organization.change(identity, value)
        except AccessDenied:
            raise HTTPException(403, "Access denied") from None
        except ManagementError as error:
            raise HTTPException(error.status, error.code) from None
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.middleware("http")
    async def private_responses(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    return app
