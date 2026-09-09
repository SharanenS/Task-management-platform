"""Celery application configuration."""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "enterprise_task_platform",
    broker=settings.RABBITMQ_URL,
    include=["app.tasks.jobs"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_backend=None,  # PostgreSQL is the durable source of truth
    broker_connection_retry_on_startup=True,
)
