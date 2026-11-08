import secrets
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from kombu import Connection, Exchange, Producer
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import WorkEventStatus, WorkOutboxEvent
from app.observability import format_traceparent, parse_traceparent, telemetry

EXCHANGE = Exchange("work.domain", type="direct", durable=True)
ROUTING_KEYS = {
    "TASK_COMPLETED": "work.task.completed.v1",
    "TASK_ASSIGNED": "work.task.assigned.v1",
}


def claim_events(
    session: Session, *, now: datetime | None = None, limit: int = 20
) -> list[WorkOutboxEvent]:
    claimed_at = now or datetime.now(UTC)
    events = list(
        session.scalars(
            select(WorkOutboxEvent)
            .where(
                or_(
                    and_(
                        WorkOutboxEvent.status.in_(
                            [WorkEventStatus.PENDING, WorkEventStatus.FAILED]
                        ),
                        WorkOutboxEvent.available_at <= claimed_at,
                    ),
                    and_(
                        WorkOutboxEvent.status == WorkEventStatus.IN_FLIGHT,
                        WorkOutboxEvent.lease_expires_at <= claimed_at,
                    ),
                )
            )
            .order_by(WorkOutboxEvent.created_at, WorkOutboxEvent.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    for event in events:
        event.status = WorkEventStatus.IN_FLIGHT
        event.lease_token = secrets.token_hex(24)
        event.lease_expires_at = claimed_at + timedelta(seconds=30)
        event.attempt_count += 1
    session.commit()
    return events


def settle_success(session: Session, event_id: UUID, lease_token: str) -> bool:
    current = session.get(WorkOutboxEvent, event_id)
    if not current or not secrets.compare_digest(current.lease_token or "", lease_token):
        return False
    current.status = WorkEventStatus.PUBLISHED
    current.published_at = datetime.now(UTC)
    current.lease_token = None
    current.lease_expires_at = None
    current.last_failure_classification = None
    return True


def settle_failure(session: Session, event_id: UUID, lease_token: str) -> bool:
    current = session.get(WorkOutboxEvent, event_id)
    if not current or not secrets.compare_digest(current.lease_token or "", lease_token):
        return False
    current.status = WorkEventStatus.FAILED
    current.available_at = datetime.now(UTC) + timedelta(
        seconds=min(60, 2 ** min(current.attempt_count, 5))
    )
    current.lease_token = None
    current.lease_expires_at = None
    current.last_failure_classification = "PUBLICATION_FAILED"
    return True


def publish_once() -> int:
    with SessionLocal() as session:
        events = claim_events(session)
        for event in events:
            try:
                payload = {
                    "eventId": str(event.id),
                    "schemaVersion": event.schema_version,
                    "eventType": event.event_type,
                    "projectId": str(event.project_id),
                    "taskId": str(event.task_id),
                    "actorEmployeeId": str(event.actor_employee_id),
                    "recipientEmployeeId": (
                        str(event.recipient_employee_id) if event.recipient_employee_id else None
                    ),
                    "taskVersion": event.task_version,
                    "occurredAt": event.created_at.isoformat(),
                }
                parent_trace_id = None
                parent_span_id = None
                if event.traceparent:
                    parsed = parse_traceparent(event.traceparent)
                    if parsed:
                        parent_trace_id, parent_span_id, _ = parsed
                span = telemetry.start_span(
                    "publish_work_event",
                    parent_trace_id=parent_trace_id,
                    parent_span_id=parent_span_id,
                    attributes={
                        "messaging.system": "rabbitmq",
                        "messaging.destination": EXCHANGE.name,
                        "messaging.routing_key": ROUTING_KEYS[event.event_type],
                        "event.id": str(event.id),
                        "event.type": event.event_type,
                    },
                )
                with span:
                    headers = {
                        "x-correlation-id": event.correlation_id or str(event.id),
                        "traceparent": format_traceparent(span.trace_id, span.span_id),
                    }
                    with Connection(settings.rabbitmq_url, connect_timeout=5) as connection:
                        Producer(connection).publish(
                            payload,
                            headers=headers,
                            exchange=EXCHANGE,
                            routing_key=ROUTING_KEYS[event.event_type],
                            serializer="json",
                            declare=[EXCHANGE],
                            delivery_mode=2,
                            retry=False,
                            confirm_publish=True,
                        )
                    settle_success(session, event.id, event.lease_token or "")
                    telemetry.logger.info(
                        "work_event_published", event_id=str(event.id), event_type=event.event_type
                    )
            except Exception:
                settle_failure(session, event.id, event.lease_token or "")
            finally:
                telemetry.flush()
            session.commit()
        return len(events)


def main() -> None:
    while True:
        publish_once()
        time.sleep(2)


if __name__ == "__main__":
    main()
