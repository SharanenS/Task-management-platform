import csv
import hashlib
import io
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx

from app.config import settings

MAX_EXPORT_ROWS = 500
MAX_RESULT_BYTES = 256_000
CSV_COLUMNS = ("reference", "title", "status", "priority", "assignee", "due_date")


class ExecutionFailure(Exception):
    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class ExportResult:
    content: str
    content_type: str
    checksum: str
    row_count: int
    truncated: bool


def safe_cell(value: object) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def render_csv(items: list[dict[str, Any]], *, truncated: bool) -> ExportResult:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for item in items[:MAX_EXPORT_ROWS]:
        writer.writerow(
            {
                "reference": safe_cell(item.get("reference")),
                "title": safe_cell(item.get("title")),
                "status": safe_cell(item.get("status")),
                "priority": safe_cell(item.get("priority")),
                "assignee": safe_cell(item.get("assigneeDisplayName")),
                "due_date": safe_cell(item.get("dueDate")),
            }
        )
    content = output.getvalue()
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_RESULT_BYTES:
        raise ExecutionFailure("RESULT_TOO_LARGE", retryable=False)
    return ExportResult(
        content=content,
        content_type="text/csv; charset=utf-8",
        checksum=hashlib.sha256(encoded).hexdigest(),
        row_count=min(len(items), MAX_EXPORT_ROWS),
        truncated=truncated or len(items) > MAX_EXPORT_ROWS,
    )


def _get(
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, str | int | bool] | None = None,
) -> Any:
    try:
        response = httpx.get(url, headers=headers, params=params, timeout=8.0)
    except httpx.HTTPError as error:
        raise ExecutionFailure("DEPENDENCY_UNAVAILABLE", retryable=True) from error
    if response.status_code >= 500:
        raise ExecutionFailure("DEPENDENCY_UNAVAILABLE", retryable=True)
    if response.status_code == 404:
        raise ExecutionFailure("RESOURCE_UNAVAILABLE", retryable=False)
    if response.status_code >= 400:
        raise ExecutionFailure("ACCESS_REVOKED", retryable=False)
    try:
        return response.json()
    except ValueError as error:
        raise ExecutionFailure("DEPENDENCY_UNAVAILABLE", retryable=True) from error


def execute_project_task_export(
    submitter_employee_id: UUID, payload: dict[str, object]
) -> ExportResult:
    employee = _get(
        f"{settings.employee_service_url}/internal/execution/employees/{submitter_employee_id}",
        headers={"X-Job-Worker-Service-Key": settings.worker_employee_service_key},
    )
    if not employee.get("active"):
        raise ExecutionFailure("SUBMITTER_INACTIVE", retryable=False)
    try:
        project_id = UUID(str(payload["projectId"]))
        include_completed = bool(payload["includeCompleted"])
        role = str(employee["role"])
    except (KeyError, TypeError, ValueError) as error:
        raise ExecutionFailure("INVALID_PAYLOAD", retryable=False) from error
    task_data = _get(
        f"{settings.work_service_url}/internal/execution/projects/{project_id}/tasks",
        headers={
            "X-Job-Worker-Service-Key": settings.worker_work_service_key,
            "X-Actor-Employee-Id": str(submitter_employee_id),
            "X-Actor-Application-Role": role,
        },
        params={"include_completed": include_completed, "limit": MAX_EXPORT_ROWS},
    )
    items = task_data.get("items")
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise ExecutionFailure("DEPENDENCY_UNAVAILABLE", retryable=True)
    return render_csv(items, truncated=bool(task_data.get("truncated")))
