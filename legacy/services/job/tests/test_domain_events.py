import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import domain_event_publisher
from app.db import Base
from app.domain_event_publisher import claim_events, settle_failure, settle_success
from app.models import DomainEventStatus, Job, JobDomainEvent, JobStatus, JobType


@pytest.fixture
def session() -> Generator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as value:
        yield value


def create_event(session: Session) -> JobDomainEvent:
    job_id = uuid.uuid4()
    job = Job(
        id=job_id,
        job_type=JobType.PROJECT_TASK_EXPORT,
        status=JobStatus.SUCCEEDED,
        submitter_employee_id=uuid.uuid4(),
        related_project_id=uuid.uuid4(),
        payload={"projectId": str(uuid.uuid4()), "format": "CSV", "includeCompleted": True},
        request_fingerprint="a" * 64,
        idempotency_key=uuid.uuid4().hex,
    )
    event = JobDomainEvent(
        job_id=job_id,
        event_type="REPORT_SUCCEEDED",
        recipient_employee_id=job.submitter_employee_id,
        project_id=job.related_project_id,
    )
    session.add_all([job, event])
    session.commit()
    return event


def test_domain_event_claim_fencing_and_non_regression(session: Session) -> None:
    event = create_event(session)
    start = datetime.now(UTC)
    first = claim_events(session, now=start)[0]
    old_token = first.lease_token or ""
    assert claim_events(session, now=start + timedelta(seconds=29)) == []
    current = claim_events(session, now=start + timedelta(seconds=31))[0]
    assert current.lease_token and current.lease_token != old_token
    assert not settle_success(session, event.id, old_token)
    assert settle_success(session, event.id, current.lease_token)
    session.refresh(event)
    assert event.status == DomainEventStatus.PUBLISHED
    assert claim_events(session, now=start + timedelta(days=1)) == []


def test_domain_event_failure_is_bounded_and_reclaimable(session: Session) -> None:
    event = create_event(session)
    claimed = claim_events(session)[0]
    assert settle_failure(session, event.id, claimed.lease_token or "")
    session.refresh(event)
    assert event.status == DomainEventStatus.FAILED
    assert event.last_failure_classification == "PUBLICATION_FAILED"
    assert claim_events(session, now=event.available_at - timedelta(milliseconds=1)) == []
    assert claim_events(session, now=event.available_at)[0].id == event.id
    assert session.scalar(select(JobDomainEvent).where(JobDomainEvent.id == event.id))


def test_terminal_event_publication_preserves_exact_ownership(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = create_event(session)
    published: list[tuple[dict[str, object], dict[str, object]]] = []

    @contextmanager
    def sessions() -> Generator[Session]:
        yield session

    class Connection:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def __enter__(self) -> "Connection":
            return self

        def __exit__(self, *_: object) -> None:
            return None

    class Producer:
        def __init__(self, _: object) -> None:
            pass

        def publish(self, body: dict[str, object], **values: object) -> None:
            published.append((body, values))

    monkeypatch.setattr(domain_event_publisher, "SessionLocal", sessions)
    monkeypatch.setattr(domain_event_publisher, "Connection", Connection)
    monkeypatch.setattr(domain_event_publisher, "Producer", Producer)

    assert domain_event_publisher.publish_once() == 1
    assert len(published) == 1
    body, values = published[0]
    assert body == {
        "eventId": str(event.id),
        "schemaVersion": 1,
        "eventType": "REPORT_SUCCEEDED",
        "recipientEmployeeId": str(event.recipient_employee_id),
        "projectId": str(event.project_id),
        "reportId": str(event.job_id),
        "reportType": "PROJECT_TASK_EXPORT",
        "occurredAt": event.created_at.isoformat(),
    }
    assert values["exchange"] is domain_event_publisher.EXCHANGE
    assert values["routing_key"] == domain_event_publisher.ROUTING_KEY
    session.refresh(event)
    assert event.status == DomainEventStatus.PUBLISHED


def test_terminal_event_publication_propagates_persisted_traceparent(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = create_event(session)
    event.correlation_id = "bounded-job-correlation-456"
    event.traceparent = "00-5bf92f3577b34da6a3ce929d0e0e4736-00e067aa0ba902b7-01"
    session.commit()

    published: list[tuple[dict[str, object], dict[str, object]]] = []
    exported_spans = []

    @contextmanager
    def sessions() -> Generator[Session]:
        yield session

    class Connection:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def __enter__(self) -> "Connection":
            return self

        def __exit__(self, *_: object) -> None:
            return None

    class Producer:
        def __init__(self, _: object) -> None:
            pass

        def publish(self, body: dict[str, object], **values: object) -> None:
            published.append((body, values))

    from app.observability import telemetry

    monkeypatch.setattr(domain_event_publisher, "SessionLocal", sessions)
    monkeypatch.setattr(domain_event_publisher, "Connection", Connection)
    monkeypatch.setattr(domain_event_publisher, "Producer", Producer)
    monkeypatch.setattr(telemetry, "export_span", lambda s: exported_spans.append(s))

    assert domain_event_publisher.publish_once() == 1
    assert len(published) == 1
    _, values = published[0]
    headers = values.get("headers", {})
    assert headers.get("x-correlation-id") == "bounded-job-correlation-456"
    assert "traceparent" in headers
    assert headers["traceparent"].startswith("00-5bf92f3577b34da6a3ce929d0e0e4736-")
    assert len(exported_spans) == 1
    span = exported_spans[0]
    assert span.trace_id == "5bf92f3577b34da6a3ce929d0e0e4736"
    assert span.parent_span_id == "00e067aa0ba902b7"


def test_domain_event_publish_with_unavailable_exporter(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = create_event(session)
    event.correlation_id = "bounded-job-correlation-789"
    event.traceparent = "00-5bf92f3577b34da6a3ce929d0e0e4736-00e067aa0ba902b7-01"
    session.commit()

    published: list[tuple[dict[str, object], dict[str, object]]] = []

    @contextmanager
    def sessions() -> Generator[Session]:
        yield session

    class Connection:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def __enter__(self) -> "Connection":
            return self

        def __exit__(self, *_: object) -> None:
            return None

    class Producer:
        def __init__(self, _: object) -> None:
            pass

        def publish(self, body: dict[str, object], **values: object) -> None:
            published.append((body, values))

    from app.observability import BoundedOTLPTraceExporter, telemetry

    failing_exporter = BoundedOTLPTraceExporter(
        endpoint="http://127.0.0.1:59999/unreachable", service_name="job"
    )
    monkeypatch.setattr(telemetry, "exporter", failing_exporter)
    monkeypatch.setattr(domain_event_publisher, "SessionLocal", sessions)
    monkeypatch.setattr(domain_event_publisher, "Connection", Connection)
    monkeypatch.setattr(domain_event_publisher, "Producer", Producer)

    assert domain_event_publisher.publish_once() == 1
    assert len(published) == 1
    session.refresh(event)
    assert event.status == DomainEventStatus.PUBLISHED
