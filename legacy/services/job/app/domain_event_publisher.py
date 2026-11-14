import secrets
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from kombu import Connection, Exchange, Producer
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import DomainEventStatus, JobDomainEvent
from app.observability import format_traceparent, parse_traceparent, telemetry

EXCHANGE = Exchange("job.domain", type="direct", durable=True)
ROUTING_KEY = "job.report.terminal.v1"


def claim_events(
    session: Session, *, now: datetime | None = None, limit: int = 20
) -> list[JobDomainEvent]:
    claimed_at = now or datetime.now(UTC)
    events = list(
        session.scalars(
            select(JobDomainEvent)
            .where(
                or_(
                    and_(
                        JobDomainEvent.status.in_(
                            [DomainEventStatus.PENDING, DomainEventStatus.FAILED]
                        ),
                        JobDomainEvent.available_at <= claimed_at,
                    ),
                    and_(
                        JobDomainEvent.status == DomainEventStatus.IN_FLIGHT,
                        JobDomainEvent.lease_expires_at <= claimed_at,
                    ),
                )
            )
            .order_by(JobDomainEvent.created_at, JobDomainEvent.id)
            .limit(min(max(limit, 1), 100))
            .with_for_update(skip_locked=True)
        )
    )
    for event in events:
        event.status = DomainEventStatus.IN_FLIGHT
        event.lease_token = secrets.token_hex(24)
        event.lease_expires_at = claimed_at + timedelta(seconds=30)
        event.attempt_count += 1
    session.commit()
    return events


def settle_success(session: Session, event_id: UUID, token: str) -> bool:
    event = session.scalar(
        select(JobDomainEvent).where(JobDomainEvent.id == event_id).with_for_update()
    )
    if (
        not event
        or event.status != DomainEventStatus.IN_FLIGHT
        or not secrets.compare_digest(event.lease_token or "", token)
    ):
        session.rollback()
        return False
    event.status = DomainEventStatus.PUBLISHED
    event.published_at = datetime.now(UTC)
    event.lease_token = None
    event.lease_expires_at = None
    event.last_failure_classification = None
    session.commit()
    return True


def settle_failure(session: Session, event_id: UUID, token: str) -> bool:
    event = session.scalar(
        select(JobDomainEvent).where(JobDomainEvent.id == event_id).with_for_update()
    )
    if (
        not event
        or event.status != DomainEventStatus.IN_FLIGHT
        or not secrets.compare_digest(event.lease_token or "", token)
    ):
        session.rollback()
        return False
    event.status = DomainEventStatus.FAILED
    event.available_at = datetime.now(UTC) + timedelta(
        seconds=min(60, 2 ** min(event.attempt_count, 5))
    )
    event.lease_token = None
    event.lease_expires_at = None
    event.last_failure_classification = "PUBLICATION_FAILED"
    session.commit()
    return True


def publish_once() -> int:
    with SessionLocal() as session:
        events = claim_events(session)
        for event in events:
            token = event.lease_token or ""
            try:
                parent_trace_id = None
                parent_span_id = None
                if getattr(event, "traceparent", None):
                    parsed = parse_traceparent(event.traceparent)
                    if parsed:
                        parent_trace_id, parent_span_id, _ = parsed
                span = telemetry.start_span(
                    "publish_job_domain_event",
                    parent_trace_id=parent_trace_id,
                    parent_span_id=parent_span_id,
                    attributes={
                        "messaging.system": "rabbitmq",
                        "messaging.destination": EXCHANGE.name,
                        "messaging.routing_key": ROUTING_KEY,
                        "event.id": str(event.id),
                        "event.type": event.event_type,
                        "job.id": str(event.job_id),
                    },
                )
                with span:
                    headers = {
                        "x-correlation-id": getattr(event, "correlation_id", None) or str(event.id),
                        "traceparent": format_traceparent(span.trace_id, span.span_id),
                    }
                    with Connection(settings.rabbitmq_url, connect_timeout=5) as connection:
                        Producer(connection).publish(
                            {
                                "eventId": str(event.id),
                                "schemaVersion": event.schema_version,
                                "eventType": event.event_type,
                                "recipientEmployeeId": str(event.recipient_employee_id),
                                "projectId": str(event.project_id) if event.project_id else None,
                                "reportId": str(event.job_id),
                                "reportType": "PROJECT_TASK_EXPORT",
                                "occurredAt": event.created_at.isoformat(),
                            },
                            headers=headers,
                            exchange=EXCHANGE,
                            routing_key=ROUTING_KEY,
                            serializer="json",
                            declare=[EXCHANGE],
                            delivery_mode=2,
                            retry=False,
                            confirm_publish=True,
                        )
                settle_success(session, event.id, token)
            except Exception:
                settle_failure(session, event.id, token)
            finally:
                telemetry.flush()
        return len(events)


def main() -> None:
    while True:
        publish_once()
        time.sleep(2)


if __name__ == "__main__":
    main()
