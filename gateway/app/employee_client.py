from dataclasses import dataclass

import httpx

from app.config import settings


class EmployeeForbiddenError(Exception):
    pass


class EmployeeUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class EmployeeProfile:
    id: str
    display_name: str
    email: str
    role: str


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
