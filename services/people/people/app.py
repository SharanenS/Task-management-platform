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


def create_app(settings=None, sessions=None, verifier=None):
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

    @app.get("/internal/actor")
    def actor(request: Request):
        service_key = request.headers.get("x-service-key", "")
        if not service_key.isascii() or not compare_digest(service_key, settings.service_key):
            raise HTTPException(401, "Authentication required")
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "Authentication required")
        try:
            identity = verifier.verify(authorization[7:])
        except Exception:
            raise HTTPException(401, "Authentication required") from None
        try:
            with sessions() as session:
                value = resolve_actor(session, identity)
                return asdict(value)
        except AccessDenied:
            raise HTTPException(403, "Access denied") from None
        except Exception:
            raise HTTPException(503, "Service unavailable") from None

    @app.middleware("http")
    async def private_responses(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    return app
