from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import consumer
from app.db import Base
from app.models import Notification, SourceEvent


class Message:
    def __init__(self) -> None:
        self.acked = False
        self.rejected: bool | None = None

    def ack(self) -> None:
        self.acked = True

    def reject(self, *, requeue: bool) -> None:
        self.rejected = requeue


def task_event(recipient: object, event_id: object | None = None) -> dict[str, object]:
    return {
        "eventId": str(event_id or uuid4()),
        "schemaVersion": 1,
        "eventType": "TASK_ASSIGNED",
        "recipientEmployeeId": str(recipient),
        "projectId": str(uuid4()),
        "taskId": str(uuid4()),
        "actorEmployeeId": str(uuid4()),
        "taskVersion": 2,
        "credential": "must-not-be-copied",
    }


@pytest.fixture
def boundary(monkeypatch: pytest.MonkeyPatch) -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)

    @contextmanager
    def sessions():
        yield session

    monkeypatch.setattr(consumer, "SessionLocal", sessions)
    yield session
    session.close()


def test_assignment_duplicate_and_post_commit_retry_are_idempotent(boundary: Session) -> None:
    event_id, recipient = uuid4(), uuid4()
    body = task_event(recipient, event_id)
    first, retry = Message(), Message()
    consumer.handle(body, first)
    consumer.handle(body, retry)
    assert first.acked and retry.acked


def test_consumer_ack_with_unavailable_exporter(
    boundary: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.observability import BoundedOTLPTraceExporter, telemetry

    failing_exporter = BoundedOTLPTraceExporter(
        endpoint="http://127.0.0.1:59999/unreachable", service_name="notification"
    )
    monkeypatch.setattr(telemetry, "exporter", failing_exporter)

    event_id, recipient = uuid4(), uuid4()
    body = task_event(recipient, event_id)
    msg = Message()
    msg.headers = {"traceparent": "00-5bf92f3577b34da6a3ce929d0e0e4736-00e067aa0ba902b7-01"}

    consumer.handle(body, msg)
    assert msg.acked
    stmt = select(Notification).where(Notification.source_event_id == event_id)
    assert boundary.scalar(stmt) is not None
    notifications = list(boundary.scalars(select(Notification)))
    assert len(notifications) == 1 and notifications[0].recipient_employee_id == recipient
    assert "credential" not in notifications[0].message


@pytest.mark.parametrize("event_type", ["REPORT_SUCCEEDED", "REPORT_FAILED"])
def test_report_terminal_events_create_safe_requester_notification(
    boundary: Session, event_type: str
) -> None:
    recipient = uuid4()
    event_id, project_id, report_id = uuid4(), uuid4(), uuid4()
    body = task_event(recipient, event_id)
    body.update(
        {
            "eventType": event_type,
            "projectId": str(project_id),
            "reportId": str(report_id),
            "reportType": "PROJECT_TASK_EXPORT",
        }
    )
    message = Message()
    consumer.handle(body, message)
    item = boundary.scalar(select(Notification))
    assert message.acked and item and item.recipient_employee_id == recipient
    assert item.notification_type.value == event_type
    assert item.source_event_id == event_id
    assert item.project_id == project_id and item.report_id == report_id
    source = boundary.get(SourceEvent, item.source_event_id)
    assert source and source.status.value == "PROCESSED" and source.event_type == event_type


@pytest.mark.parametrize(
    "change,expected_code",
    [
        ({"schemaVersion": 2}, "UNSUPPORTED_SCHEMA"),
        ({"eventType": "UNKNOWN"}, "UNSUPPORTED_EVENT"),
        ({"recipientEmployeeId": "invalid"}, "INVALID_EVENT"),
        ({"taskId": None}, "INVALID_EVENT"),
        ({"taskVersion": "two"}, "INVALID_EVENT"),
    ],
)
def test_permanent_invalid_messages_are_rejected_without_persistence(
    boundary: Session, change: dict[str, object], expected_code: str
) -> None:
    body = task_event(uuid4())
    body.update(change)
    message = Message()
    consumer.handle(body, message)
    assert message.rejected is False and not message.acked
    assert boundary.scalar(select(SourceEvent)) is None
    assert boundary.scalar(select(Notification)) is None


def test_non_mapping_payload_is_rejected_without_persistence(boundary: Session) -> None:
    message = Message()
    consumer.handle("malformed-json", message)
    assert message.rejected is False
    assert boundary.scalar(select(SourceEvent)) is None


def test_self_assignment_and_unsupported_report_type_are_rejected(boundary: Session) -> None:
    recipient = uuid4()
    assignment = task_event(recipient)
    assignment["actorEmployeeId"] = str(recipient)
    first = Message()
    consumer.handle(assignment, first)
    report = task_event(recipient)
    report.update(
        {
            "eventType": "REPORT_SUCCEEDED",
            "reportId": str(uuid4()),
            "reportType": "UNSUPPORTED",
        }
    )
    second = Message()
    consumer.handle(report, second)
    assert first.rejected is False and second.rejected is False
    assert boundary.scalar(select(Notification)) is None


def test_infrastructure_failure_is_left_for_broker_redelivery(
    boundary: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(*_: object, **__: object) -> None:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(consumer, "receive_event", unavailable)
    message = Message()
    with pytest.raises(RuntimeError, match="database unavailable"):
        consumer.handle(task_event(uuid4()), message)
    assert not message.acked and message.rejected is None
