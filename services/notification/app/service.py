import base64
import binascii
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import InboxStatus, Notification, NotificationType, SourceEvent


class NotificationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code


@dataclass(frozen=True)
class Page:
    items: list[Notification]
    next_cursor: str | None
    has_next_page: bool


def _cursor(item: Notification) -> str:
    raw = json.dumps([item.created_at.isoformat(), str(item.id)], separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode(value: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        timestamp, identifier = json.loads(raw)
        return datetime.fromisoformat(timestamp), UUID(identifier)
    except (ValueError, TypeError, json.JSONDecodeError, binascii.Error) as error:
        raise NotificationError("INVALID_CURSOR", "The notification cursor is invalid.") from error


def list_notifications(
    session: Session, recipient: UUID, *, first: int, after: str | None, unread_only: bool
) -> Page:
    if first < 1 or first > 50:
        raise NotificationError("INVALID_PAGE_SIZE", "The page size must be between 1 and 50.")
    query = select(Notification).where(Notification.recipient_employee_id == recipient)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    if after:
        created, identifier = _decode(after)
        query = query.where(
            or_(
                Notification.created_at < created,
                and_(Notification.created_at == created, Notification.id < identifier),
            )
        )
    items = list(
        session.scalars(
            query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(first + 1)
        )
    )
    return Page(
        items[:first], _cursor(items[first - 1]) if len(items) > first else None, len(items) > first
    )


def unread_count(session: Session, recipient: UUID) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.recipient_employee_id == recipient, Notification.read_at.is_(None))
        )
        or 0
    )


def mark_read(session: Session, recipient: UUID, notification_id: UUID) -> Notification:
    item = session.scalar(
        select(Notification)
        .where(
            Notification.id == notification_id,
            Notification.recipient_employee_id == recipient,
        )
        .with_for_update()
    )
    if item is None:
        raise NotificationError("NOT_FOUND", "The notification was not found.", 404)
    if item.read_at is None:
        item.read_at = datetime.now(UTC)
        session.commit()
    return item


def mark_all_read(session: Session, recipient: UUID) -> int:
    count = unread_count(session, recipient)
    session.execute(
        update(Notification)
        .where(Notification.recipient_employee_id == recipient, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    session.commit()
    return count


def receive_event(session: Session, payload: dict[str, object]) -> Notification | None:
    try:
        event_id = UUID(str(payload["eventId"]))
        event_type = str(payload["eventType"])
        version = payload["schemaVersion"]
        recipient = UUID(str(payload["recipientEmployeeId"]))
    except (KeyError, TypeError, ValueError) as error:
        raise NotificationError("INVALID_EVENT", "The notification event is invalid.") from error
    if version != 1:
        raise NotificationError(
            "UNSUPPORTED_SCHEMA", "The notification event schema is unsupported."
        )
    existing = session.scalar(
        select(Notification).where(
            Notification.recipient_employee_id == recipient,
            Notification.source_event_id == event_id,
        )
    )
    if existing:
        return existing
    supported = {
        "TASK_ASSIGNED": (
            NotificationType.TASK_ASSIGNED,
            "Task assigned",
            "A task was assigned to you.",
        ),
        "REPORT_SUCCEEDED": (
            NotificationType.REPORT_SUCCEEDED,
            "Report ready",
            "Your report is ready to download.",
        ),
        "REPORT_FAILED": (
            NotificationType.REPORT_FAILED,
            "Report failed",
            "Your report could not be completed.",
        ),
    }
    if event_type not in supported:
        raise NotificationError("UNSUPPORTED_EVENT", "The notification event type is unsupported.")
    try:
        if event_type == "TASK_ASSIGNED":
            UUID(str(payload["projectId"]))
            UUID(str(payload["taskId"]))
            actor = UUID(str(payload["actorEmployeeId"]))
            if actor == recipient or not isinstance(payload["taskVersion"], int):
                raise ValueError
        else:
            UUID(str(payload["reportId"]))
            if payload["reportType"] != "PROJECT_TASK_EXPORT":
                raise NotificationError(
                    "UNSUPPORTED_REPORT", "The notification report type is unsupported."
                )
    except NotificationError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise NotificationError("INVALID_EVENT", "The notification event is invalid.") from error
    source = session.get(SourceEvent, event_id)
    if source and source.status != InboxStatus.RECEIVED:
        return session.scalar(select(Notification).where(Notification.source_event_id == event_id))
    if source is None:
        source = SourceEvent(
            id=event_id,
            event_type=event_type,
            schema_version=1,
            status=InboxStatus.RECEIVED,
            failure_classification=None,
        )
        session.add(source)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            return session.scalar(
                select(Notification).where(
                    Notification.recipient_employee_id == recipient,
                    Notification.source_event_id == event_id,
                )
            )
    category, title, message = supported[event_type]

    def optional_uuid(name: str) -> UUID | None:
        value = payload.get(name)
        return UUID(str(value)) if value else None

    item = Notification(
        recipient_employee_id=recipient,
        notification_type=category,
        title=title,
        message=message,
        source_event_id=event_id,
        project_id=optional_uuid("projectId"),
        task_id=optional_uuid("taskId"),
        report_id=optional_uuid("reportId"),
    )
    session.add(item)
    source.status = InboxStatus.PROCESSED
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return session.scalar(
            select(Notification).where(
                Notification.recipient_employee_id == recipient,
                Notification.source_event_id == event_id,
            )
        )
    session.refresh(item)
    return item
