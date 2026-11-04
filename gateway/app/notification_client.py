from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings
from app.employee_client import EmployeeProfile


class NotificationDomainError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


class NotificationUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class NotificationRecord:
    id: str
    recipient_employee_id: str
    notification_type: str
    title: str
    message: str
    source_event_id: str
    project_id: str | None
    task_id: str | None
    report_id: str | None
    read_at: str | None
    created_at: str


@dataclass(frozen=True)
class Page:
    items: list[NotificationRecord]
    next_cursor: str | None
    has_next_page: bool


def _record(data: dict[str, Any]) -> NotificationRecord:
    try:
        return NotificationRecord(
            data["id"],
            data["recipient_employee_id"],
            data["notification_type"],
            data["title"],
            data["message"],
            data["source_event_id"],
            data.get("project_id"),
            data.get("task_id"),
            data.get("report_id"),
            data.get("read_at"),
            data["created_at"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise NotificationUnavailableError from error


async def _request(
    method: str,
    path: str,
    actor: EmployeeProfile,
    *,
    params: dict[str, str | int | bool | None] | None = None,
) -> Any:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.request(
                method,
                f"{settings.notification_service_url}{path}",
                headers={
                    "X-Internal-Service-Key": settings.notification_internal_service_key,
                    "X-Actor-Employee-Id": actor.id,
                },
                params=params,
            )
    except httpx.HTTPError as error:
        raise NotificationUnavailableError from error
    if response.status_code >= 400:
        try:
            detail = response.json()["detail"]
            raise NotificationDomainError(detail["code"], detail["message"])
        except NotificationDomainError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise NotificationUnavailableError from error
    try:
        return response.json()
    except ValueError as error:
        raise NotificationUnavailableError from error


async def list_notifications(actor: EmployeeProfile, **params: str | int | bool | None) -> Page:
    data = await _request("GET", "/internal/notifications", actor, params=params)
    return Page(
        [_record(item) for item in data["items"]], data.get("next_cursor"), data["has_next_page"]
    )


async def unread_count(actor: EmployeeProfile) -> int:
    data = await _request("GET", "/internal/notifications/unread-count", actor)
    return int(data["count"])


async def mark_read(actor: EmployeeProfile, notification_id: str) -> NotificationRecord:
    return _record(await _request("PUT", f"/internal/notifications/{notification_id}/read", actor))


async def mark_all_read(actor: EmployeeProfile) -> int:
    data = await _request("PUT", "/internal/notifications/read-all", actor)
    return int(data["updated_count"])
