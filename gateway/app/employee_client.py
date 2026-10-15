from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings


class EmployeeForbiddenError(Exception):
    pass


class EmployeeUnavailableError(Exception):
    pass


class EmployeeDomainError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class EmployeeProfile:
    id: str
    display_name: str
    email: str
    role: str


@dataclass(frozen=True)
class EmployeeAdminProfile:
    id: str
    username: str
    display_name: str
    email: str
    role: str
    active: bool
    provisioning_status: str
    created_at: str
    updated_at: str
    version: int


@dataclass(frozen=True)
class EmployeeAdminPage:
    items: list[EmployeeAdminProfile]
    next_cursor: str | None
    has_next_page: bool


@dataclass(frozen=True)
class EligibleEmployee:
    id: str
    display_name: str
    email: str


@dataclass(frozen=True)
class EligibleEmployeePage:
    items: list[EligibleEmployee]
    next_cursor: str | None
    has_next_page: bool


def _eligible_employee(data: dict[str, Any]) -> EligibleEmployee:
    try:
        return EligibleEmployee(data["id"], data["display_name"], data["email"])
    except (KeyError, TypeError, ValueError) as error:
        raise EmployeeUnavailableError from error


def _admin_profile(data: dict[str, Any]) -> EmployeeAdminProfile:
    try:
        return EmployeeAdminProfile(
            id=data["id"],
            username=data["username"],
            display_name=data["display_name"],
            email=data["email"],
            role=data["role"],
            active=data["active"],
            provisioning_status=data["provisioning_status"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            version=data["version"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise EmployeeUnavailableError from error


async def _admin_request(
    method: str,
    path: str,
    actor_subject: str,
    *,
    params: dict[str, str | int | bool] | None = None,
    json: dict[str, object] | None = None,
) -> Any:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.request(
                method,
                f"{settings.employee_service_url}{path}",
                headers={
                    "X-Internal-Service-Key": settings.internal_service_key,
                    "X-Actor-Subject": actor_subject,
                },
                params=params,
                json=json,
            )
    except httpx.HTTPError as error:
        raise EmployeeUnavailableError from error
    if response.status_code >= 400:
        try:
            detail = response.json()["detail"]
            code = detail["code"]
            message = detail["message"]
            if not isinstance(code, str) or not isinstance(message, str):
                raise ValueError
            raise EmployeeDomainError(code, message)
        except EmployeeDomainError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise EmployeeUnavailableError from error
    try:
        return response.json()
    except ValueError as error:
        raise EmployeeUnavailableError from error


async def list_admin_employees(
    actor_subject: str,
    *,
    first: int,
    after: str | None,
    search: str | None,
    role: str | None,
    active: bool | None,
) -> EmployeeAdminPage:
    data = await _admin_request(
        "GET",
        "/internal/admin/employees",
        actor_subject,
        params={
            "first": first,
            **({"after": after} if after else {}),
            **({"search": search} if search else {}),
            **({"role": role} if role else {}),
            **({"active": active} if active is not None else {}),
        },
    )
    try:
        return EmployeeAdminPage(
            items=[_admin_profile(item) for item in data["items"]],
            next_cursor=data.get("next_cursor"),
            has_next_page=data["has_next_page"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise EmployeeUnavailableError from error


async def get_admin_employee(actor_subject: str, employee_id: str) -> EmployeeAdminProfile:
    return _admin_profile(
        await _admin_request("GET", f"/internal/admin/employees/{employee_id}", actor_subject)
    )


async def provision_admin_employee(
    actor_subject: str, payload: dict[str, object]
) -> EmployeeAdminProfile:
    return _admin_profile(
        await _admin_request("POST", "/internal/admin/employees", actor_subject, json=payload)
    )


async def update_admin_employee_role(
    actor_subject: str, employee_id: str, role: str
) -> EmployeeAdminProfile:
    return _admin_profile(
        await _admin_request(
            "PUT",
            f"/internal/admin/employees/{employee_id}/role",
            actor_subject,
            json={"role": role},
        )
    )


async def update_admin_employee_active(
    actor_subject: str, employee_id: str, active: bool
) -> EmployeeAdminProfile:
    return _admin_profile(
        await _admin_request(
            "PUT",
            f"/internal/admin/employees/{employee_id}/active",
            actor_subject,
            json={"active": active},
        )
    )


async def reconcile_admin_employee(actor_subject: str, employee_id: str) -> EmployeeAdminProfile:
    return _admin_profile(
        await _admin_request(
            "POST", f"/internal/admin/employees/{employee_id}/reconcile", actor_subject
        )
    )


async def list_eligible_employees(
    actor_subject: str, *, first: int, after: str | None, search: str | None
) -> EligibleEmployeePage:
    data = await _admin_request(
        "GET",
        "/internal/project-members/eligible",
        actor_subject,
        params={
            "first": first,
            **({"after": after} if after else {}),
            **({"search": search} if search else {}),
        },
    )
    try:
        return EligibleEmployeePage(
            [_eligible_employee(item) for item in data["items"]],
            data.get("next_cursor"),
            data["has_next_page"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise EmployeeUnavailableError from error


async def validate_eligible_employee(actor_subject: str, employee_id: str) -> EligibleEmployee:
    return _eligible_employee(
        await _admin_request(
            "GET", f"/internal/project-members/{employee_id}/validate", actor_subject
        )
    )


async def resolve_employee_references(
    actor_subject: str, employee_ids: list[str]
) -> list[EligibleEmployee]:
    data = await _admin_request(
        "POST",
        "/internal/project-members/resolve",
        actor_subject,
        json={"employee_ids": employee_ids},
    )
    if not isinstance(data, list):
        raise EmployeeUnavailableError
    return [_eligible_employee(item) for item in data]


async def get_employee(subject: str) -> EmployeeProfile:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.employee_service_url}/internal/employees/by-subject/{subject}",
                headers={"X-Internal-Service-Key": settings.internal_service_key},
            )
    except httpx.HTTPError as error:
        raise EmployeeUnavailableError from error
    if response.status_code in {403, 404}:
        raise EmployeeForbiddenError
    if response.status_code != 200:
        raise EmployeeUnavailableError
    try:
        data = response.json()
        return EmployeeProfile(
            id=data["id"],
            display_name=data["display_name"],
            email=data["email"],
            role=data["role"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise EmployeeUnavailableError from error
