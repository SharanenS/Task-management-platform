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


@dataclass(frozen=True)
class WorkProjectMetrics:
    total_count: int
    active_count: int
    draft_count: int
    archived_count: int
    managed_total_count: int | None
    managed_active_count: int | None
    managed_draft_count: int | None
    managed_archived_count: int | None


@dataclass(frozen=True)
class WorkTaskMetrics:
    total_count: int
    todo_count: int
    in_progress_count: int
    blocked_count: int
    done_count: int
    cancelled_count: int
    overdue_count: int


@dataclass(frozen=True)
class WorkDashboardTaskItem:
    id: str
    project_id: str
    project_key: str
    number: int
    title: str
    status: str
    priority: str
    due_date: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class WorkDashboardMetrics:
    project_metrics: WorkProjectMetrics
    task_metrics: WorkTaskMetrics | None
    assigned_task_metrics: WorkTaskMetrics
    recent_projects: list[WorkProject]
    recent_assigned_tasks: list[WorkDashboardTaskItem]


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


async def get_dashboard_metrics(actor: EmployeeProfile) -> WorkDashboardMetrics:
    data = await _request("GET", "/internal/dashboard/metrics", actor)
    try:
        p_metrics = data["project_metrics"]
        project_metrics = WorkProjectMetrics(
            total_count=p_metrics["total_count"],
            active_count=p_metrics["active_count"],
            draft_count=p_metrics["draft_count"],
            archived_count=p_metrics["archived_count"],
            managed_total_count=p_metrics.get("managed_total_count"),
            managed_active_count=p_metrics.get("managed_active_count"),
            managed_draft_count=p_metrics.get("managed_draft_count"),
            managed_archived_count=p_metrics.get("managed_archived_count"),
        )
        task_metrics = None
        if data.get("task_metrics"):
            t_metrics = data["task_metrics"]
            task_metrics = WorkTaskMetrics(
                total_count=t_metrics["total_count"],
                todo_count=t_metrics["todo_count"],
                in_progress_count=t_metrics["in_progress_count"],
                blocked_count=t_metrics["blocked_count"],
                done_count=t_metrics["done_count"],
                cancelled_count=t_metrics["cancelled_count"],
                overdue_count=t_metrics["overdue_count"],
            )
        a_metrics = data["assigned_task_metrics"]
        assigned_task_metrics = WorkTaskMetrics(
            total_count=a_metrics["total_count"],
            todo_count=a_metrics["todo_count"],
            in_progress_count=a_metrics["in_progress_count"],
            blocked_count=a_metrics["blocked_count"],
            done_count=a_metrics["done_count"],
            cancelled_count=a_metrics["cancelled_count"],
            overdue_count=a_metrics["overdue_count"],
        )
        recent_projects = [_project(item) for item in data["recent_projects"]]
        recent_assigned_tasks = [
            WorkDashboardTaskItem(
                id=item["id"],
                project_id=item["project_id"],
                project_key=item["project_key"],
                number=item["number"],
                title=item["title"],
                status=item["status"],
                priority=item["priority"],
                due_date=item.get("due_date"),
                created_at=item["created_at"],
                updated_at=item["updated_at"],
            )
            for item in data["recent_assigned_tasks"]
        ]
        return WorkDashboardMetrics(
            project_metrics=project_metrics,
            task_metrics=task_metrics,
            assigned_task_metrics=assigned_task_metrics,
            recent_projects=recent_projects,
            recent_assigned_tasks=recent_assigned_tasks,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise WorkUnavailableError from error
