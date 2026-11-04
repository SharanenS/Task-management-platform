import hmac
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.schemas import MarkAllResult, NotificationPage, NotificationResponse, UnreadCount
from app.service import (
    NotificationError,
    list_notifications,
    mark_all_read,
    mark_read,
    unread_count,
)

app = FastAPI(title="Notification Service", docs_url=None, redoc_url=None, openapi_url=None)
SessionDependency = Annotated[Session, Depends(get_session)]


def require_internal(x_internal_service_key: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_internal_service_key, settings.internal_service_key):
        raise HTTPException(403, "Forbidden")


def recipient(x_actor_employee_id: str = Header(default="")) -> UUID:
    try:
        return UUID(x_actor_employee_id)
    except ValueError as error:
        raise HTTPException(403, "Forbidden") from error


Recipient = Annotated[UUID, Depends(recipient)]


def failure(error: NotificationError) -> HTTPException:
    return HTTPException(error.status_code, {"code": error.code, "message": error.message})


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def ready(session: SessionDependency) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get(
    "/internal/notifications",
    response_model=NotificationPage,
    dependencies=[Depends(require_internal)],
)
def notifications(
    session: SessionDependency,
    actor: Recipient,
    first: int = Query(20, ge=1, le=50),
    after: str | None = None,
    unread_only: bool = False,
) -> NotificationPage:
    try:
        page = list_notifications(session, actor, first=first, after=after, unread_only=unread_only)
        return NotificationPage(
            items=[NotificationResponse.model_validate(item) for item in page.items],
            next_cursor=page.next_cursor,
            has_next_page=page.has_next_page,
        )
    except NotificationError as error:
        raise failure(error) from error


@app.get(
    "/internal/notifications/unread-count",
    response_model=UnreadCount,
    dependencies=[Depends(require_internal)],
)
def count(session: SessionDependency, actor: Recipient) -> UnreadCount:
    return UnreadCount(count=unread_count(session, actor))


@app.put(
    "/internal/notifications/{notification_id}/read",
    response_model=NotificationResponse,
    dependencies=[Depends(require_internal)],
)
def read(
    notification_id: UUID, session: SessionDependency, actor: Recipient
) -> NotificationResponse:
    try:
        return NotificationResponse.model_validate(mark_read(session, actor, notification_id))
    except NotificationError as error:
        raise failure(error) from error


@app.put(
    "/internal/notifications/read-all",
    response_model=MarkAllResult,
    dependencies=[Depends(require_internal)],
)
def read_all(session: SessionDependency, actor: Recipient) -> MarkAllResult:
    return MarkAllResult(updated_count=mark_all_read(session, actor))
