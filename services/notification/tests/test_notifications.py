from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Notification, SourceEvent
from app.service import (
    NotificationError,
    list_notifications,
    mark_all_read,
    mark_read,
    receive_event,
    unread_count,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as value:
        yield value


def event(recipient: object, event_id: object | None = None) -> dict[str, object]:
    return {
        "eventId": str(event_id or uuid4()),
        "schemaVersion": 1,
        "eventType": "TASK_ASSIGNED",
        "recipientEmployeeId": str(recipient),
        "projectId": str(uuid4()),
        "taskId": str(uuid4()),
        "actorEmployeeId": str(uuid4()),
        "taskVersion": 2,
    }


def test_owner_pagination_unread_and_marking(session: Session) -> None:
    owner, foreign = uuid4(), uuid4()
    first = receive_event(session, event(owner))
    receive_event(session, event(owner))
    receive_event(session, event(foreign))
    assert first is not None
    page = list_notifications(session, owner, first=1, after=None, unread_only=True)
    assert len(page.items) == 1 and page.has_next_page and page.next_cursor
    assert (
        len(
            list_notifications(
                session, owner, first=2, after=page.next_cursor, unread_only=False
            ).items
        )
        == 1
    )
    assert unread_count(session, owner) == 2
    mark_read(session, owner, first.id)
    assert unread_count(session, owner) == 1
    assert mark_all_read(session, owner) == 1
    assert unread_count(session, owner) == 0
    assert unread_count(session, foreign) == 1
    with pytest.raises(NotificationError, match="not found"):
        mark_read(session, foreign, first.id)


def test_duplicate_and_unsupported_delivery(session: Session) -> None:
    owner, identifier = uuid4(), uuid4()
    payload = event(owner, identifier)
    first = receive_event(session, payload)
    second = receive_event(session, payload)
    assert first is not None and second is not None and first.id == second.id
    assert len(list(session.scalars(select(Notification)))) == 1
    unsupported = event(owner)
    unsupported["eventType"] = "UNKNOWN"
    with pytest.raises(NotificationError, match="unsupported"):
        receive_event(session, unsupported)
    assert len(list(session.scalars(select(SourceEvent)))) == 1


def test_report_terminal_event_is_safe_and_private(session: Session) -> None:
    owner, report_id = uuid4(), uuid4()
    payload = event(owner)
    payload.update(
        {
            "eventType": "REPORT_SUCCEEDED",
            "reportId": str(report_id),
            "reportType": "PROJECT_TASK_EXPORT",
        }
    )
    item = receive_event(session, payload)
    assert item is not None
    assert item.report_id == report_id
    assert item.title == "Report ready"
    assert "http" not in item.message


def test_validation_and_rollback(session: Session) -> None:
    with pytest.raises(NotificationError, match="invalid"):
        receive_event(session, {"eventId": "secret", "schemaVersion": 1})
    assert session.scalar(select(Notification)) is None
    assert session.scalar(select(SourceEvent)) is None
    with pytest.raises(NotificationError, match="page size"):
        list_notifications(session, uuid4(), first=0, after=None, unread_only=False)
