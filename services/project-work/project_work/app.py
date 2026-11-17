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
from .service import CalendarService, identifier


def create_app(
    settings=None, sessions=None, verifier=None, people_transport=None, service_key=None
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
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def authority(request):
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
                        people_url.rstrip("/") + "/internal/admin/workspace",
                        headers={
                            "Authorization": authorization,
                            "X-Service-Key": settings.service_key,
                        },
                    )
                if response.status_code in {401, 403}:
                    raise HTTPException(403, "Access denied")
                response.raise_for_status()
                actor = response.json()
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

    @app.get("/health/live")
    def live():
        return {"status": "up"}

    @app.get("/health/ready")
    def ready():
        try:
            with sessions() as s:
                s.execute(text("SELECT 1 FROM calendar_versions LIMIT 1"))
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
