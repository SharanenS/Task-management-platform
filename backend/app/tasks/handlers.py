"""Handler registry and execution functions for background jobs."""

from collections.abc import Callable
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Type alias for a job handler function: takes payload dict, returns structured result
JobHandler = Callable[[dict[str, Any] | None], Any]

HANDLERS: dict[str, JobHandler] = {}


def register_handler(job_type: str) -> Callable[[JobHandler], JobHandler]:
    """Decorator to register a job execution handler by job_type."""
    def decorator(func: JobHandler) -> JobHandler:
        HANDLERS[job_type] = func
        return func
    return decorator


def get_handler(job_type: str) -> JobHandler | None:
    """Retrieve the registered handler for a job type, or None if unknown."""
    return HANDLERS.get(job_type)


# ── Demonstration Handlers ──────────────────────────────────────────────────

@register_handler("REPORT_GENERATION")
def handle_report_generation(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Demonstration handler: process report generation."""
    payload = payload or {}
    if payload.get("simulate_failure"):
        msg = payload.get("error_message") or "Report generation failed: data corruption detected"
        raise ValueError(msg)

    report_type = payload.get("report_type", "summary")
    logger.info("report_generation_handler_executed", report_type=report_type)
    return {"status": "success", "report_type": report_type, "records_processed": 100}


@register_handler("DATA_EXPORT")
def handle_data_export(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Demonstration handler: process data export."""
    payload = payload or {}
    if payload.get("simulate_failure"):
        msg = payload.get("error_message") or "Data export failed: disk quota exceeded"
        raise ValueError(msg)

    target_format = payload.get("format", "csv")
    logger.info("data_export_handler_executed", format=target_format)
    return {"status": "success", "format": target_format, "rows_exported": 500}


@register_handler("CLEANUP")
def handle_cleanup(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Demonstration handler: process system cleanup."""
    payload = payload or {}
    if payload.get("simulate_failure"):
        msg = payload.get("error_message") or "Cleanup failed: permission denied on target resource"
        raise ValueError(msg)

    retention_days = payload.get("retention_days", 30)
    logger.info("cleanup_handler_executed", retention_days=retention_days)
    return {"status": "success", "cleaned_items": 15}
