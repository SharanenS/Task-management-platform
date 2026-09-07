"""Global error handler middleware."""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppException
from app.core.logging import get_logger

logger = get_logger(__name__)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle custom application exceptions."""
    logger.warning(
        "app_exception",
        detail=exc.detail,
        status_code=exc.status_code,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )