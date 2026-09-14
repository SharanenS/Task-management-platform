"""Health check endpoints (liveness and readiness)."""

import asyncio
from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger, sanitize_error
from app.db.session import engine

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
@router.get("/liveness")
async def liveness() -> dict[str, Any]:
    """
    Liveness probe: proves the FastAPI process is alive and responsive.
    Lightweight and fast; does NOT probe external dependencies like DB or broker.
    """
    return {
        "status": "alive",
        "version": settings.APP_VERSION,
    }


@router.get("/ready")
@router.get("/readiness")
async def readiness(response: Response) -> dict[str, Any]:
    """
    Readiness probe: proves genuine dependencies required for the API are operational.
    Probes PostgreSQL with a short timeout.
    Returns HTTP 200 when ready, or HTTP 503 when required dependencies fail.
    Never leaks connection strings, credentials, or sensitive tokens.
    """
    checks: dict[str, str] = {}
    is_ready = True

    # Probe PostgreSQL (required API dependency)
    try:
        async with asyncio.timeout(3.0):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        checks["database"] = "available"
    except Exception as exc:
        is_ready = False
        checks["database"] = "unavailable"
        logger.warning("readiness_check_failed", dependency="database", error=sanitize_error(str(exc)))

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "error",
            "checks": checks,
        }

    return {
        "status": "ready",
        "checks": checks,
    }
