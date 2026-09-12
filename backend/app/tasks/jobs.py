"""Celery tasks for asynchronous job processing."""

import asyncio
import uuid

from app.core.celery_app import celery_app
from app.core.logging import get_logger
from app.tasks.executor import execute_job_by_id

logger = get_logger(__name__)


@celery_app.task(name="app.tasks.process_job")
def process_job_task(job_id: str, claim_owner: str | None = None) -> None:
    """
    Celery task entrypoint receiving durable job ID and optional recovery claim owner.
    Dispatches to the asynchronous execution engine.
    """
    logger.info("celery_task_received", job_id=job_id, claim_owner=claim_owner)
    try:
        parsed_id = uuid.UUID(job_id)
    except (ValueError, TypeError) as e:
        logger.error("invalid_job_id_format", job_id=job_id, error=str(e))
        return

    if claim_owner is not None:
        asyncio.run(execute_job_by_id(parsed_id, claim_owner=claim_owner))
    else:
        asyncio.run(execute_job_by_id(parsed_id))
