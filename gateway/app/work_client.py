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
