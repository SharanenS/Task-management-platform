"""Health check endpoint."""

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/liveness")
async def liveness():
    """Check if the FastAPI application is alive."""
    return {"status": "alive", "version": settings.APP_VERSION}

@router.get("/readiness")
async def readiness(response: Response):
    """Check if the backend can connect to PostgreSQL."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error"}