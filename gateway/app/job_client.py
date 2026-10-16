from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings
from app.employee_client import EmployeeProfile


class JobUnavailableError(Exception):
    pass


class JobDomainError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


@dataclass(frozen=True)
class JobRecord:
    id: str
    job_type: str
    status: str
    submitter_employee_id: str
    related_project_id: str | None
    payload: dict[str, object]
    result_summary: str | None
    failure_classification: str | None
    version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class JobPage:
    items: list[JobRecord]
    next_cursor: str | None
    has_next_page: bool


@dataclass(frozen=True)
class JobAttemptRecord:
    id: str
    attempt_number: int
    status: str
    created_at: str


def _job(data: dict[str, Any]) -> JobRecord:
    try:
        payload = data["payload"]
        if not isinstance(payload, dict):
            raise TypeError
        return JobRecord(
            data["id"],
            data["job_type"],
            data["status"],
            data["submitter_employee_id"],
            data.get("related_project_id"),
            payload,
            data.get("result_summary"),
            data.get("failure_classification"),
            data["version"],
            data["created_at"],
            data["updated_at"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise JobUnavailableError from error


async def _request(
    method: str,
    path: str,
    actor: EmployeeProfile,
    *,
    params: dict[str, str | int] | None = None,
    json: dict[str, object] | None = None,
) -> Any:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.request(
                method,
                f"{settings.job_service_url}{path}",
                headers={
                    "X-Internal-Service-Key": settings.job_internal_service_key,
                    "X-Actor-Employee-Id": actor.id,
                    "X-Actor-Application-Role": actor.role,
                },
                params=params,
                json=json,
            )
    except httpx.HTTPError as error:
        raise JobUnavailableError from error
    if response.status_code >= 400:
        try:
            detail = response.json()["detail"]
            code, message = detail["code"], detail["message"]
            if not isinstance(code, str) or not isinstance(message, str):
                raise ValueError
            raise JobDomainError(code, message)
        except JobDomainError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise JobUnavailableError from error
    try:
        return response.json()
    except ValueError as error:
        raise JobUnavailableError from error


async def list_jobs(
    actor: EmployeeProfile,
    *,
    first: int,
    after: str | None,
    status: str | None,
    job_type: str | None,
) -> JobPage:
    data = await _request(
        "GET",
        "/internal/jobs",
        actor,
        params={
            "first": first,
            **({"after": after} if after else {}),
            **({"status": status} if status else {}),
            **({"job_type": job_type} if job_type else {}),
        },
    )
    try:
        return JobPage(
            [_job(item) for item in data["items"]],
            data.get("next_cursor"),
            data["has_next_page"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise JobUnavailableError from error


async def get_job(actor: EmployeeProfile, job_id: str) -> JobRecord:
    return _job(await _request("GET", f"/internal/jobs/{job_id}", actor))


async def list_attempts(actor: EmployeeProfile, job_id: str) -> list[JobAttemptRecord]:
    data = await _request("GET", f"/internal/jobs/{job_id}/attempts", actor)
    try:
        return [
            JobAttemptRecord(item["id"], item["attempt_number"], item["status"], item["created_at"])
            for item in data["items"]
        ]
    except (KeyError, TypeError, ValueError) as error:
        raise JobUnavailableError from error


async def submit_job(
    actor: EmployeeProfile, *, project_id: str, include_completed: bool, idempotency_key: str
) -> JobRecord:
    return _job(
        await _request(
            "POST",
            "/internal/jobs",
            actor,
            json={
                "job_type": "PROJECT_TASK_EXPORT",
                "payload": {
                    "project_id": project_id,
                    "format": "CSV",
                    "include_completed": include_completed,
                },
                "idempotency_key": idempotency_key,
            },
        )
    )
