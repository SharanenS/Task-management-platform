"""Celery tasks for asynchronous job processing."""

import asyncio
import uuid

from app.core.celery_app import celery_app
from app.core.logging import get_logger
from app.tasks.executor import execute_job_by_id

logger = get_logger(__name__)


@celery_app.task(name="app.tasks.process_job")
def process_job_task(job_id: str) -> None:
    """Celery task entrypoint receiving durable job ID and running execution."""
    logger.info("celery_task_received", job_id=job_id)
    try:
        parsed_id = uuid.UUID(job_id)
    except (ValueError, TypeError) as e:
        logger.error("invalid_job_id_format", job_id=job_id, error=str(e))
        return

    asyncio.run(execute_job_by_id(parsed_id))
