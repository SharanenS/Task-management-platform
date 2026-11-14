import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models import InboxStatus, Notification, SourceEvent
from app.service import (
    NotificationError,
    list_notifications,
    mark_all_read,
    mark_read,
    receive_event,
)

DATABASE_URL = os.getenv("NOTIFICATION_POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="NOTIFICATION_POSTGRES_TEST_URL is required."
)


@pytest.fixture
def factory() -> sessionmaker[Session]:
    assert DATABASE_URL
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    maker = sessionmaker(engine, expire_on_commit=False)
    with maker() as session:
        session.execute(delete(Notification))
        session.execute(delete(SourceEvent))
        session.commit()
    yield maker
    with maker() as session:
        session.execute(delete(Notification))
        session.execute(delete(SourceEvent))
        session.commit()
    engine.dispose()


def payload(recipient: object, event_id: object | None = None) -> dict[str, object]:
    return {
        "eventId": str(event_id or uuid4()),
        "schemaVersion": 1,
        "eventType": "TASK_ASSIGNED",
        "recipientEmployeeId": str(recipient),
        "projectId": str(uuid4()),
        "taskId": str(uuid4()),
        "actorEmployeeId": str(uuid4()),
        "taskVersion": 2,
        "sensitive": "must-not-be-copied",
    }


def test_recipient_cursor_unread_and_concealed_mutations(factory: sessionmaker[Session]) -> None:
    owner, foreign = uuid4(), uuid4()
    with factory() as session:
        older = receive_event(session, payload(owner))
        newer = receive_event(session, payload(owner))
        receive_event(session, payload(foreign))
        assert older and newer
        older.created_at = datetime.now(UTC) - timedelta(minutes=1)
        newer.created_at = datetime.now(UTC)
        session.commit()
        page = list_notifications(session, owner, first=1, after=None, unread_only=True)
        assert [item.id for item in page.items] == [newer.id]
        assert page.next_cursor
        assert [
            item.id
            for item in list_notifications(
                session, owner, first=1, after=page.next_cursor, unread_only=True
            ).items
        ] == [older.id]
        with pytest.raises(NotificationError) as error:
            mark_read(session, foreign, newer.id)
        assert (error.value.code, error.value.message) == (
            "NOT_FOUND",
            "The notification was not found.",
        )
        assert mark_all_read(session, owner) == 2
        assert mark_all_read(session, owner) == 0


def test_concurrent_duplicate_delivery_creates_one_logical_notification(
    factory: sessionmaker[Session],
) -> None:
    recipient, event_id = uuid4(), uuid4()
    body = payload(recipient, event_id)
    barrier = Barrier(2)

    def deliver() -> object:
        with factory() as session:
            barrier.wait()
            item = receive_event(session, body)
            return item.id if item else None

    with ThreadPoolExecutor(max_workers=2) as pool:
        identifiers = list(pool.map(lambda _: deliver(), range(2)))
    assert identifiers[0] == identifiers[1] and identifiers[0] is not None
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(SourceEvent)) == 1
        assert session.scalar(select(func.count()).select_from(Notification)) == 1


def test_transaction_rollback_and_source_cascade(factory: sessionmaker[Session]) -> None:
    recipient, event_id = uuid4(), uuid4()
    with factory() as session:
        source = SourceEvent(
            id=event_id,
            event_type="TASK_ASSIGNED",
            schema_version=1,
            status=InboxStatus.RECEIVED,
        )
        session.add(source)
        session.flush()
        session.add(
            Notification(
                recipient_employee_id=recipient,
                notification_type="TASK_ASSIGNED",
                title="Task assigned",
                message="A task was assigned to you.",
                source_event_id=event_id,
            )
        )
        session.rollback()
        assert session.get(SourceEvent, event_id) is None
        assert session.scalar(select(Notification)) is None

        item = receive_event(session, payload(recipient, event_id))
        assert item
        notification_id = item.id
        session.delete(session.get(SourceEvent, event_id))
        session.commit()
        session.expire_all()
        assert session.get(Notification, notification_id) is None


def test_source_event_allows_only_one_notification(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        item = receive_event(session, payload(uuid4()))
        assert item is not None
        session.add(
            Notification(
                recipient_employee_id=uuid4(),
                notification_type="TASK_ASSIGNED",
                title="Task assigned",
                message="A task was assigned to you.",
                source_event_id=item.source_event_id,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        assert (
            session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.source_event_id == item.source_event_id)
            )
            == 1
        )


def test_malformed_and_unsupported_events_persist_no_unsafe_content(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        with pytest.raises(NotificationError):
            receive_event(session, {"eventId": "credential-value"})
        assert session.scalar(select(Notification)) is None
        body = payload(uuid4())
        body["eventType"] = "UNSUPPORTED"
        with pytest.raises(NotificationError) as error:
            receive_event(session, body)
        assert error.value.code == "UNSUPPORTED_EVENT"
        assert session.scalar(select(SourceEvent)) is None
