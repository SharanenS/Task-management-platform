from typing import Any
from uuid import UUID

from celery import Celery
from kombu.exceptions import ChannelError, OperationalError

from app.observability import format_traceparent, parse_traceparent, telemetry


class PublishFailure(Exception):
    def __init__(
        self, classification: str = "PUBLICATION_FAILED", *, ambiguous: bool | None = None
    ) -> None:
        super().__init__("Job publication failed.")
        self.classification = "CONFIRMATION_AMBIGUOUS" if ambiguous else classification
        self.ambiguous = self.classification == "CONFIRMATION_AMBIGUOUS"


TASK_NAME = "job.execute_project_task_export"
QUEUE_NAME = "job.execution"
ROUTING_KEY = "job.execute"


class CeleryPublisher:
    def __init__(self, celery: Celery) -> None:
        self.celery = celery

    def publish(
        self,
        job_id: UUID,
        event_id: UUID | None = None,
        traceparent: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        parent_trace_id = None
        parent_span_id = None
        if traceparent:
            parsed = parse_traceparent(traceparent)
            if parsed:
                parent_trace_id, parent_span_id, _ = parsed
        span = telemetry.start_span(
            "publish_job_task",
            parent_trace_id=parent_trace_id,
            parent_span_id=parent_span_id,
            attributes={
                "messaging.system": "celery",
                "messaging.destination": QUEUE_NAME,
                "job.id": str(job_id),
            },
        )
        with span:
            cid = correlation_id or span.trace_id
            tp = format_traceparent(span.trace_id, span.span_id)
            tracing_headers = {
                "X-Correlation-ID": cid,
                "traceparent": tp,
            }
            kwargs: dict[str, Any] = {
                "queue": QUEUE_NAME,
                "routing_key": ROUTING_KEY,
                "serializer": "json",
                "retry": False,
                "delivery_mode": 2,
                "confirm_publish": True,
                "headers": tracing_headers,
            }
            if event_id:
                kwargs["task_id"] = str(event_id)
            try:
                self.celery.send_task(
                    TASK_NAME,
                    args=[str(job_id)],
                    **kwargs,
                )
            except OperationalError as error:
                raise PublishFailure("CONNECTION_FAILED") from error
            except ChannelError as error:
                raise PublishFailure("CONFIRMATION_REJECTED") from error
            except TimeoutError as error:
                raise PublishFailure("CONFIRMATION_AMBIGUOUS") from error
        telemetry.flush()


def publisher() -> CeleryPublisher:
    from app.celery_app import celery_app

    return CeleryPublisher(celery_app)
