"""Celery tasks for email delivery (placeholder)."""

from app.tasks.celery_app import celery_app


@celery_app.task
def send_email(to: str, subject: str, body: str) -> dict:
    """Send an email (placeholder for future implementation)."""
    # TODO: Implement email sending (e.g., via SES, SendGrid)
    return {"to": to, "subject": subject, "status": "sent"}