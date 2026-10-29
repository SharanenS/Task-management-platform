from dataclasses import dataclass
from typing import Any, cast

import httpx

from app.config import settings
from app.employee_client import EmployeeProfile


class WorkflowDomainError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


class WorkflowUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class Rule:
    id: str
    project_id: str
    name: str
    trigger_type: str
    action_type: str
    enabled: bool
    creator_employee_id: str
    version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Execution:
    id: str
    rule_id: str
    source_event_id: str
    project_id: str
    task_id: str
    status: str
    resulting_job_id: str | None
    failure_classification: str | None
    created_at: str
    updated_at: str
    completed_at: str | None


@dataclass(frozen=True)
class Page:
    items: list[Any]
    next_cursor: str | None
    has_next_page: bool


def _rule(data: dict[str, Any]) -> Rule:
    try:
        return Rule(
            data["id"],
            data["project_id"],
            data["name"],
            data["trigger_type"],
            data["action_type"],
            data["enabled"],
            data["creator_employee_id"],
            data["version"],
            data["created_at"],
            data["updated_at"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise WorkflowUnavailableError from error


def _execution(data: dict[str, Any]) -> Execution:
    try:
        return Execution(
            data["id"],
            data["rule_id"],
            data["source_event_id"],
            data["project_id"],
            data["task_id"],
            data["status"],
            data.get("resulting_job_id"),
            data.get("failure_classification"),
            data["created_at"],
            data["updated_at"],
            data.get("completed_at"),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise WorkflowUnavailableError from error


async def _request(
    method: str,
    path: str,
    actor: EmployeeProfile,
    *,
    project_ids: list[str],
    managed_project_ids: list[str],
    params: dict[str, object] | None = None,
    json: dict[str, object] | None = None,
) -> Any:
    headers = {
        "X-Internal-Service-Key": settings.workflow_internal_service_key,
        "X-Actor-Employee-Id": actor.id,
        "X-Actor-Application-Role": actor.role,
        "X-Actor-Project-Ids": ",".join(project_ids),
        "X-Actor-Managed-Project-Ids": ",".join(managed_project_ids),
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.request(
                method,
                f"{settings.workflow_service_url}{path}",
                headers=headers,
                params=cast(Any, params),
                json=json,
            )
    except httpx.HTTPError as error:
        raise WorkflowUnavailableError from error
    if response.status_code >= 400:
        try:
            detail = response.json()["detail"]
            raise WorkflowDomainError(detail["code"], detail["message"])
        except WorkflowDomainError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise WorkflowUnavailableError from error
    try:
        return response.json()
    except ValueError as error:
        raise WorkflowUnavailableError from error


async def list_rules(
    actor: EmployeeProfile, project_ids: list[str], managed: list[str], **params: object
) -> Page:
    data = await _request(
        "GET",
        "/internal/rules",
        actor,
        project_ids=project_ids,
        managed_project_ids=managed,
        params=params,
    )
    return Page(
        [_rule(item) for item in data["items"]], data.get("next_cursor"), data["has_next_page"]
    )


async def get_rule(
    actor: EmployeeProfile, rule_id: str, project_ids: list[str], managed: list[str]
) -> Rule:
    return _rule(
        await _request(
            "GET",
            f"/internal/rules/{rule_id}",
            actor,
            project_ids=project_ids,
            managed_project_ids=managed,
        )
    )


async def create_rule(
    actor: EmployeeProfile, body: dict[str, object], project_ids: list[str], managed: list[str]
) -> Rule:
    return _rule(
        await _request(
            "POST",
            "/internal/rules",
            actor,
            project_ids=project_ids,
            managed_project_ids=managed,
            json=body,
        )
    )


async def update_rule(
    actor: EmployeeProfile,
    rule_id: str,
    body: dict[str, object],
    project_ids: list[str],
    managed: list[str],
    *,
    state: bool = False,
) -> Rule:
    suffix = "/state" if state else ""
    return _rule(
        await _request(
            "PUT",
            f"/internal/rules/{rule_id}{suffix}",
            actor,
            project_ids=project_ids,
            managed_project_ids=managed,
            json=body,
        )
    )


async def list_executions(
    actor: EmployeeProfile, project_ids: list[str], managed: list[str], **params: object
) -> Page:
    data = await _request(
        "GET",
        "/internal/executions",
        actor,
        project_ids=project_ids,
        managed_project_ids=managed,
        params=params,
    )
    return Page(
        [_execution(item) for item in data["items"]], data.get("next_cursor"), data["has_next_page"]
    )


async def get_execution(
    actor: EmployeeProfile, execution_id: str, project_ids: list[str], managed: list[str]
) -> Execution:
    return _execution(
        await _request(
            "GET",
            f"/internal/executions/{execution_id}",
            actor,
            project_ids=project_ids,
            managed_project_ids=managed,
        )
    )
