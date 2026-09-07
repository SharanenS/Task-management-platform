"""Celery periodic tasks for cleanup."""

from app.tasks.celery_app import celery_app


@celery_app.task
def cleanup_expired_reports() -> dict:
    """Remove expired report files from S3 (placeholder)."""
    # TODO: Implement cleanup logic
    return {"status": "completed", "removed": 0}


@celery_app.task
def cleanup_old_notifications() -> dict:
    """Remove notifications older than 90 days (placeholder)."""
    # TODO: Implement cleanup logic
    return {"status": "completed", "removed": 0}