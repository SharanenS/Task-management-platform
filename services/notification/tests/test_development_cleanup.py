import sys
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import development_cleanup
from app.config import settings
from app.db import Base
from app.models import InboxStatus, Notification, NotificationType, SourceEvent


def factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def add_notification(values: sessionmaker[Session], recipient: UUID) -> tuple[UUID, UUID]:
    with values() as session:
        source = SourceEvent(
            id=uuid4(),
            event_type="TASK_ASSIGNED",
            schema_version=1,
            status=InboxStatus.PROCESSED,
        )
        item = Notification(
            recipient_employee_id=recipient,
            notification_type=NotificationType.TASK_ASSIGNED,
            title="Task assigned",
            message="A task was assigned.",
            source_event_id=source.id,
            project_id=uuid4(),
            task_id=uuid4(),
        )
        session.add_all([source, item])
        session.commit()
        return item.id, source.id


def test_cleanup_removes_only_exact_owned_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    values = factory()
    recipient, foreign = uuid4(), uuid4()
    owned_id, owned_source = add_notification(values, recipient)
    foreign_id, foreign_source = add_notification(values, foreign)
    monkeypatch.setattr(development_cleanup, "SessionLocal", values)

    development_cleanup.remove(owned_id, owned_source, recipient)

    with values() as session:
        assert session.get(Notification, owned_id) is None
        assert session.get(SourceEvent, owned_source) is None
        assert session.get(Notification, foreign_id) is not None
        assert session.get(SourceEvent, foreign_source) is not None


def test_cleanup_refuses_foreign_recipient(monkeypatch: pytest.MonkeyPatch) -> None:
    values = factory()
    owner = uuid4()
    notification_id, source_id = add_notification(values, owner)
    monkeypatch.setattr(development_cleanup, "SessionLocal", values)
    with pytest.raises(SystemExit, match="ownership was not verified"):
        development_cleanup.remove(notification_id, source_id, uuid4())
    with values() as session:
        assert session.get(Notification, notification_id) is not None
        assert session.get(SourceEvent, source_id) is not None


def test_cleanup_refuses_ambiguous_source_event(monkeypatch: pytest.MonkeyPatch) -> None:
    recipient, foreign = uuid4(), uuid4()
    source = SourceEvent(
        id=uuid4(), event_type="TASK_ASSIGNED", schema_version=1, status=InboxStatus.PROCESSED
    )
    owned = Notification(
        id=uuid4(),
        recipient_employee_id=recipient,
        notification_type=NotificationType.TASK_ASSIGNED,
        title="Task assigned",
        message="A task was assigned.",
        source_event_id=source.id,
    )
    other = Notification(
        id=uuid4(),
        recipient_employee_id=foreign,
        notification_type=NotificationType.TASK_ASSIGNED,
        title="Task assigned",
        message="A task was assigned.",
        source_event_id=source.id,
    )

    class FakeSession:
        deleted: list[object] = []

        def __enter__(self) -> "FakeSession":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def get(self, model: object, identifier: UUID) -> object | None:
            if model is Notification and identifier == owned.id:
                return owned
            if model is SourceEvent and identifier == source.id:
                return source
            return None

        def scalars(self, _: object) -> list[Notification]:
            return [owned, other]

        def delete(self, value: object) -> None:
            self.deleted.append(value)

        def flush(self) -> None:
            return None

        def commit(self) -> None:
            return None

    current = FakeSession()
    monkeypatch.setattr(development_cleanup, "SessionLocal", lambda: current)
    with pytest.raises(SystemExit, match="source-event ownership"):
        development_cleanup.remove(owned.id, source.id, recipient)
    assert current.deleted == []
    assert current.get(Notification, owned.id) is owned
    assert other in current.scalars(object())
    assert current.get(SourceEvent, source.id) is source


def test_cleanup_refuses_partial_ownership(monkeypatch: pytest.MonkeyPatch) -> None:
    values = factory()
    notification_id, _ = add_notification(values, uuid4())
    monkeypatch.setattr(development_cleanup, "SessionLocal", values)
    with pytest.raises(SystemExit, match="ownership is incomplete"):
        development_cleanup.remove(notification_id, uuid4(), uuid4())


def test_cleanup_rerun_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    values = factory()
    recipient = uuid4()
    notification_id, source_id = add_notification(values, recipient)
    monkeypatch.setattr(development_cleanup, "SessionLocal", values)
    development_cleanup.remove(notification_id, source_id, recipient)
    development_cleanup.remove(notification_id, source_id, recipient)


def test_cli_refuses_invalid_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "development_cleanup",
            "--notification-id",
            "not-a-uuid",
            "--source-event-id",
            str(uuid4()),
            "--recipient-employee-id",
            str(uuid4()),
        ],
    )
    with pytest.raises(SystemExit) as error:
        development_cleanup.main()
    assert error.value.code == 2


def test_cleanup_refuses_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(SystemExit, match="development or test"):
        development_cleanup.remove(uuid4(), uuid4(), uuid4())
