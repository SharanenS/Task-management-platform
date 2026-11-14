from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.event_publisher import settle_failure, settle_success
from app.models import WorkEventStatus, WorkOutboxEvent


def event() -> WorkOutboxEvent:
    return WorkOutboxEvent(
        event_type="TASK_COMPLETED",
        schema_version=1,
        project_id=uuid4(),
        task_id=uuid4(),
        actor_employee_id=uuid4(),
        task_version=2,
        status=WorkEventStatus.IN_FLIGHT,
        attempt_count=1,
        available_at=datetime.now(UTC),
        lease_token="current-token",
    )


def test_exact_token_settlement_and_stale_token_rejection() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        item = event()
        session.add(item)
        session.commit()
        assert not settle_success(session, item.id, "stale-token")
        assert item.status == WorkEventStatus.IN_FLIGHT
        assert settle_success(session, item.id, "current-token")
        assert item.status == WorkEventStatus.PUBLISHED and item.lease_token is None


def test_failure_is_bounded_and_stale_failure_cannot_regress_published_event() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        item = event()
        session.add(item)
        session.commit()
        assert settle_failure(session, item.id, "current-token")
        assert item.status == WorkEventStatus.FAILED
        assert item.last_failure_classification == "PUBLICATION_FAILED"
        assert not settle_failure(session, item.id, "current-token")


def test_publish_once_exports_span_and_injects_tracing_headers(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    item = event()
    item.status = WorkEventStatus.PENDING
    item.lease_token = None
    with Session(engine, expire_on_commit=False) as session:
        session.add(item)
        session.commit()

    published_headers = {}
    published_payload = {}

    class MockProducer:
        def __init__(self, connection):
            pass

        def publish(self, payload, headers=None, **kwargs):
            nonlocal published_headers, published_payload
            published_headers = headers or {}
            published_payload = payload

    class MockConnection:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    import app.event_publisher as ep

    monkeypatch.setattr(ep, "SessionLocal", lambda: Session(engine, expire_on_commit=False))
    monkeypatch.setattr(ep, "Connection", MockConnection)
    monkeypatch.setattr(ep, "Producer", MockProducer)

    count = ep.publish_once()
    assert count == 1
    assert published_headers.get("x-correlation-id") == str(item.id)
    assert "traceparent" in published_headers
    assert published_headers["traceparent"].startswith("00-")


def test_publish_once_extracts_persisted_traceparent_across_restart(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    item = event()
    item.status = WorkEventStatus.PENDING
    item.lease_token = None
    item.correlation_id = "bounded-req-correlation-123"
    item.traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

    with Session(engine, expire_on_commit=False) as session:
        session.add(item)
        session.commit()

    published_headers = {}
    exported_spans = []

    class MockProducer:
        def __init__(self, connection):
            pass

        def publish(self, payload, headers=None, **kwargs):
            nonlocal published_headers
            published_headers = headers or {}

    class MockConnection:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    import app.event_publisher as ep
    from app.observability import telemetry

    monkeypatch.setattr(ep, "SessionLocal", lambda: Session(engine, expire_on_commit=False))
    monkeypatch.setattr(ep, "Connection", MockConnection)
    monkeypatch.setattr(ep, "Producer", MockProducer)
    monkeypatch.setattr(telemetry, "export_span", lambda s: exported_spans.append(s))

    count = ep.publish_once()
    assert count == 1
    assert published_headers.get("x-correlation-id") == "bounded-req-correlation-123"
    assert "traceparent" in published_headers
    # Continuous trace: child span inherits trace ID from HTTP traceparent
    assert published_headers["traceparent"].startswith("00-4bf92f3577b34da6a3ce929d0e0e4736-")
    assert len(exported_spans) == 1
    span = exported_spans[0]
    assert span.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert span.parent_span_id == "00f067aa0ba902b7"
