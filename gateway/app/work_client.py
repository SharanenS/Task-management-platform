from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings
from app.employee_client import EmployeeProfile


class WorkUnavailableError(Exception):
    pass


class WorkDomainError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


@dataclass(frozen=True)
class WorkMembership:
    id: str
    employee_id: str
    role: str
    created_at: str


@dataclass(frozen=True)
class WorkProject:
    id: str
    key: str
    name: str
    description: str | None
    status: str
    creator_employee_id: str
    version: int
    created_at: str
    updated_at: str
    memberships: list[WorkMembership]


@dataclass(frozen=True)
class WorkProjectPage:
    items: list[WorkProject]
    next_cursor: str | None
    has_next_page: bool


@dataclass(frozen=True)
class WorkTask:
    id: str
    project_id: str
    number: int
    title: str
    description: str | None
    status: str
    priority: str
    assignee_employee_id: str | None
    creator_employee_id: str
    due_date: str | None
    version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class WorkTaskPage:
    items: list[WorkTask]
    next_cursor: str | None
    has_next_page: bool


@dataclass(frozen=True)
class WorkTaskLane:
    status: str
    items: list[WorkTask]
    has_more: bool


@dataclass(frozen=True)
class WorkTaskComment:
    id: str
    task_id: str
    author_employee_id: str
    body: str
    created_at: str


@dataclass(frozen=True)
class WorkTaskActivity:
    id: str
    task_id: str
    actor_employee_id: str
    activity_type: str
    change_data: dict[str, str | int | None]
    created_at: str


def _project(data: dict[str, Any]) -> WorkProject:
    try:
        return WorkProject(
            id=data["id"],
            key=data["key"],
            name=data["name"],
            description=data.get("description"),
            status=data["status"],
            creator_employee_id=data["creator_employee_id"],
            version=data["version"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            memberships=[
                WorkMembership(item["id"], item["employee_id"], item["role"], item["created_at"])
                for item in data["memberships"]
            ],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise WorkUnavailableError from error


def _task(data: dict[str, Any]) -> WorkTask:
    try:
        return WorkTask(
            id=data["id"],
            project_id=data["project_id"],
            number=data["number"],
            title=data["title"],
            description=data.get("description"),
            status=data["status"],
            priority=data["priority"],
            assignee_employee_id=data.get("assignee_employee_id"),
            creator_employee_id=data["creator_employee_id"],
            due_date=data.get("due_date"),
            version=data["version"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise WorkUnavailableError from error


async def _request(
    method: str,
    path: str,
    actor: EmployeeProfile,
    *,
    params: dict[str, str | int | bool] | None = None,
    json: dict[str, object] | None = None,
) -> Any:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.request(
                method,
                f"{settings.work_service_url}{path}",
                headers={
                    "X-Internal-Service-Key": settings.work_internal_service_key,
                    "X-Actor-Employee-Id": actor.id,
                    "X-Actor-Application-Role": actor.role,
                },
                params=params,
                json=json,
            )
    except httpx.HTTPError as error:
        raise WorkUnavailableError from error
    if response.status_code >= 400:
        try:
            detail = response.json()["detail"]
            code, message = detail["code"], detail["message"]
            if not isinstance(code, str) or not isinstance(message, str):
                raise ValueError
            raise WorkDomainError(code, message)
        except WorkDomainError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise WorkUnavailableError from error
    try:
        return response.json()
    except ValueError as error:
        raise WorkUnavailableError from error


async def list_projects(
    actor: EmployeeProfile,
    *,
    first: int,
    after: str | None,
    search: str | None,
    status: str | None,
) -> WorkProjectPage:
    data = await _request(
        "GET",
        "/internal/projects",
        actor,
        params={
            "first": first,
            **({"after": after} if after else {}),
            **({"search": search} if search else {}),
            **({"status": status} if status else {}),
        },
    )
    try:
        return WorkProjectPage(
            [_project(item) for item in data["items"]],
            data.get("next_cursor"),
            data["has_next_page"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise WorkUnavailableError from error


async def get_project(actor: EmployeeProfile, project_id: str) -> WorkProject:
    return _project(await _request("GET", f"/internal/projects/{project_id}", actor))


async def create_project(actor: EmployeeProfile, payload: dict[str, object]) -> WorkProject:
    return _project(await _request("POST", "/internal/projects", actor, json=payload))


async def update_project(
    actor: EmployeeProfile, project_id: str, payload: dict[str, object]
) -> WorkProject:
    return _project(await _request("PUT", f"/internal/projects/{project_id}", actor, json=payload))


async def change_status(
    actor: EmployeeProfile, project_id: str, payload: dict[str, object]
) -> WorkProject:
    return _project(
        await _request("PUT", f"/internal/projects/{project_id}/status", actor, json=payload)
    )


async def add_member(
    actor: EmployeeProfile, project_id: str, payload: dict[str, object]
) -> WorkProject:
    return _project(
        await _request("POST", f"/internal/projects/{project_id}/members", actor, json=payload)
    )


async def change_member_role(
    actor: EmployeeProfile, project_id: str, employee_id: str, role: str
) -> WorkProject:
    return _project(
        await _request(
            "PUT",
            f"/internal/projects/{project_id}/members/{employee_id}",
            actor,
            json={"role": role},
        )
    )


async def remove_member(actor: EmployeeProfile, project_id: str, employee_id: str) -> WorkProject:
    return _project(
        await _request("DELETE", f"/internal/projects/{project_id}/members/{employee_id}", actor)
    )


async def list_tasks(
    actor: EmployeeProfile, project_id: str, *, params: dict[str, str | int | bool]
) -> WorkTaskPage:
    data = await _request("GET", f"/internal/projects/{project_id}/tasks", actor, params=params)
    try:
        return WorkTaskPage(
            [_task(item) for item in data["items"]],
            data.get("next_cursor"),
            data["has_next_page"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise WorkUnavailableError from error


async def task_board(actor: EmployeeProfile, project_id: str, lane_size: int) -> list[WorkTaskLane]:
    data = await _request(
        "GET", f"/internal/projects/{project_id}/task-board", actor, params={"lane_size": lane_size}
    )
    try:
        return [
            WorkTaskLane(item["status"], [_task(task) for task in item["items"]], item["has_more"])
            for item in data["lanes"]
        ]
    except (KeyError, TypeError, ValueError) as error:
        raise WorkUnavailableError from error


async def get_task(actor: EmployeeProfile, project_id: str, task_id: str) -> WorkTask:
    return _task(await _request("GET", f"/internal/projects/{project_id}/tasks/{task_id}", actor))


async def create_task(
    actor: EmployeeProfile, project_id: str, payload: dict[str, object]
) -> WorkTask:
    return _task(
        await _request("POST", f"/internal/projects/{project_id}/tasks", actor, json=payload)
    )


async def update_task(
    actor: EmployeeProfile, project_id: str, task_id: str, payload: dict[str, object]
) -> WorkTask:
    return _task(
        await _request(
            "PUT", f"/internal/projects/{project_id}/tasks/{task_id}", actor, json=payload
        )
    )


async def assign_task(
    actor: EmployeeProfile, project_id: str, task_id: str, payload: dict[str, object]
) -> WorkTask:
    return _task(
        await _request(
            "PUT",
            f"/internal/projects/{project_id}/tasks/{task_id}/assignment",
            actor,
            json=payload,
        )
    )


async def change_task_status(
    actor: EmployeeProfile, project_id: str, task_id: str, payload: dict[str, object]
) -> WorkTask:
    return _task(
        await _request(
            "PUT", f"/internal/projects/{project_id}/tasks/{task_id}/status", actor, json=payload
        )
    )


async def list_task_comments(
    actor: EmployeeProfile, project_id: str, task_id: str, *, first: int, after: str | None
) -> tuple[list[WorkTaskComment], str | None, bool]:
    data = await _request(
        "GET",
        f"/internal/projects/{project_id}/tasks/{task_id}/comments",
        actor,
        params={"first": first, **({"after": after} if after else {})},
    )
    try:
        return (
            [
                WorkTaskComment(
                    item["id"],
                    item["task_id"],
                    item["author_employee_id"],
                    item["body"],
                    item["created_at"],
                )
                for item in data["items"]
            ],
            data.get("next_cursor"),
            data["has_next_page"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise WorkUnavailableError from error


async def add_task_comment(
    actor: EmployeeProfile, project_id: str, task_id: str, body: str
) -> WorkTaskComment:
    data = await _request(
        "POST",
        f"/internal/projects/{project_id}/tasks/{task_id}/comments",
        actor,
        json={"body": body},
    )
    try:
        return WorkTaskComment(
            data["id"],
            data["task_id"],
            data["author_employee_id"],
            data["body"],
            data["created_at"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise WorkUnavailableError from error


async def list_task_activity(
    actor: EmployeeProfile, project_id: str, task_id: str, *, first: int, after: str | None
) -> tuple[list[WorkTaskActivity], str | None, bool]:
    data = await _request(
        "GET",
        f"/internal/projects/{project_id}/tasks/{task_id}/activity",
        actor,
        params={"first": first, **({"after": after} if after else {})},
    )
    try:
        return (
            [
                WorkTaskActivity(
                    item["id"],
                    item["task_id"],
                    item["actor_employee_id"],
                    item["activity_type"],
                    item["change_data"],
                    item["created_at"],
                )
                for item in data["items"]
            ],
            data.get("next_cursor"),
            data["has_next_page"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise WorkUnavailableError from error
