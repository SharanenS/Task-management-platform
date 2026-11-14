import argparse
from uuid import UUID

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Notification, SourceEvent


def remove(notification_id: UUID, source_event_id: UUID, recipient_employee_id: UUID) -> None:
    if settings.app_env not in {"development", "test"}:
        raise SystemExit("Cleanup is permitted only in development or test.")
    with SessionLocal() as session:
        notification = session.get(Notification, notification_id)
        source = session.get(SourceEvent, source_event_id)
        if notification is None and source is None:
            return
        if notification is None or source is None:
            raise SystemExit("Exact notification cleanup ownership is incomplete.")
        associated = list(
            session.scalars(
                select(Notification).where(Notification.source_event_id == source_event_id)
            )
        )
        if len(associated) != 1:
            raise SystemExit("Exact source-event ownership was not verified.")
        owned = associated[0]
        if (
            owned.id != notification_id
            or owned.source_event_id != source.id
            or owned.recipient_employee_id != recipient_employee_id
        ):
            raise SystemExit("Exact notification cleanup ownership was not verified.")
        session.delete(owned)
        session.flush()
        session.delete(source)
        session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove one proven disposable notification and source event"
    )
    parser.add_argument("--notification-id", required=True, type=UUID)
    parser.add_argument("--source-event-id", required=True, type=UUID)
    parser.add_argument("--recipient-employee-id", required=True, type=UUID)
    args = parser.parse_args()
    remove(args.notification_id, args.source_event_id, args.recipient_employee_id)
    print("Disposable development notification removed.")


if __name__ == "__main__":
    main()
