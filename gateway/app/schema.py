from datetime import datetime
from enum import StrEnum
from typing import NoReturn

import strawberry
from graphql import GraphQLError
from strawberry.extensions import MaxAliasesLimiter, QueryDepthLimiter
from strawberry.types import Info

from app.auth import AuthenticationError, token_validator
from app.config import settings
from app.employee_client import (
    EmployeeAdminProfile,
    EmployeeDomainError,
    EmployeeForbiddenError,
    EmployeeUnavailableError,
    get_admin_employee,
    get_employee,
    list_admin_employees,
    provision_admin_employee,
    reconcile_admin_employee,
    update_admin_employee_active,
    update_admin_employee_role,
)


@strawberry.type
class SystemInfo:
    name: str
    version: str
    environment: str
    status: str


@strawberry.enum
class ApplicationRole(StrEnum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    MEMBER = "MEMBER"


@strawberry.enum
class ProvisioningStatus(StrEnum):
    COMPLETE = "COMPLETE"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


@strawberry.type
class Employee:
    id: strawberry.ID
    display_name: str
    email: str
    role: ApplicationRole


@strawberry.type
class AdminEmployee:
    id: strawberry.ID
    username: str
    display_name: str
    email: str
    role: ApplicationRole
    active: bool
    provisioning_status: ProvisioningStatus
    created_at: datetime
    updated_at: datetime
    version: int


@strawberry.type
class PageInfo:
    has_next_page: bool
    end_cursor: str | None


@strawberry.type
class EmployeeConnection:
    nodes: list[AdminEmployee]
    page_info: PageInfo


@strawberry.input
class ProvisionEmployeeInput:
    idempotency_key: str
    username: str
    email: str
    display_name: str
    role: ApplicationRole
    active: bool
    temporary_password: str


def _admin_employee(profile: EmployeeAdminProfile) -> AdminEmployee:
    return AdminEmployee(
        id=strawberry.ID(profile.id),
        username=profile.username,
        display_name=profile.display_name,
        email=profile.email,
        role=ApplicationRole(profile.role),
        active=profile.active,
        provisioning_status=ProvisioningStatus(profile.provisioning_status),
        created_at=datetime.fromisoformat(profile.created_at),
        updated_at=datetime.fromisoformat(profile.updated_at),
        version=profile.version,
    )


async def _admin_subject(info: Info) -> str:
    try:
        identity = token_validator.validate(info.context["authorization"])
    except AuthenticationError as error:
        raise GraphQLError(
            "Authentication is required.", extensions={"code": "UNAUTHENTICATED"}
        ) from error
    try:
        actor = await get_employee(identity.subject)
    except EmployeeForbiddenError as error:
        raise GraphQLError(
            "Administrator access is required.", extensions={"code": "FORBIDDEN"}
        ) from error
    except EmployeeUnavailableError as error:
        raise GraphQLError(
            "Employee administration is temporarily unavailable.",
            extensions={"code": "SERVICE_UNAVAILABLE"},
        ) from error
    if actor.role != ApplicationRole.ADMIN:
        raise GraphQLError("Administrator access is required.", extensions={"code": "FORBIDDEN"})
    return identity.subject


def _raise_admin_error(error: Exception) -> NoReturn:
    if isinstance(error, EmployeeDomainError):
        raise GraphQLError(error.message, extensions={"code": error.code}) from error
    if isinstance(error, EmployeeUnavailableError):
        raise GraphQLError(
            "Employee administration is temporarily unavailable.",
            extensions={"code": "SERVICE_UNAVAILABLE"},
        ) from error
    raise error


@strawberry.type
class Query:
    @strawberry.field
    def system_info(self) -> SystemInfo:
        """Public, non-sensitive gateway metadata; not aggregate service health."""
        return SystemInfo(
            name="Enterprise Task Platform Gateway",
            version="0.1.0",
            environment=settings.app_env,
            status="AVAILABLE",
        )

    @strawberry.field
    async def me(self, info: Info) -> Employee:
        try:
            identity = token_validator.validate(info.context["authorization"])
        except AuthenticationError as error:
            raise GraphQLError(
                "Authentication is required.", extensions={"code": "UNAUTHENTICATED"}
            ) from error
        try:
            profile = await get_employee(identity.subject)
        except EmployeeForbiddenError as error:
            raise GraphQLError(
                "Access is not available for this account.",
                extensions={"code": "FORBIDDEN"},
            ) from error
        except EmployeeUnavailableError as error:
            raise GraphQLError(
                "Employee profiles are temporarily unavailable.",
                extensions={"code": "SERVICE_UNAVAILABLE"},
            ) from error
        return Employee(
            id=strawberry.ID(profile.id),
            display_name=profile.display_name,
            email=profile.email,
            role=ApplicationRole(profile.role),
        )

    @strawberry.field
    async def employees(
        self,
        info: Info,
        first: int = 20,
        after: str | None = None,
        search: str | None = None,
        role: ApplicationRole | None = None,
        active: bool | None = None,
    ) -> EmployeeConnection:
        subject = await _admin_subject(info)
        try:
            page = await list_admin_employees(
                subject,
                first=first,
                after=after,
                search=search,
                role=role.value if role else None,
                active=active,
            )
        except (EmployeeDomainError, EmployeeUnavailableError) as error:
            _raise_admin_error(error)
        return EmployeeConnection(
            nodes=[_admin_employee(employee) for employee in page.items],
            page_info=PageInfo(has_next_page=page.has_next_page, end_cursor=page.next_cursor),
        )

    @strawberry.field
    async def employee(self, info: Info, id: strawberry.ID) -> AdminEmployee:
        subject = await _admin_subject(info)
        try:
            return _admin_employee(await get_admin_employee(subject, str(id)))
        except (EmployeeDomainError, EmployeeUnavailableError) as error:
            _raise_admin_error(error)


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def provision_employee(self, info: Info, input: ProvisionEmployeeInput) -> AdminEmployee:
        subject = await _admin_subject(info)
        try:
            profile = await provision_admin_employee(
                subject,
                {
                    "idempotency_key": input.idempotency_key,
                    "username": input.username,
                    "email": input.email,
                    "display_name": input.display_name,
                    "role": input.role.value,
                    "active": input.active,
                    "temporary_password": input.temporary_password,
                },
            )
            return _admin_employee(profile)
        except (EmployeeDomainError, EmployeeUnavailableError) as error:
            _raise_admin_error(error)

    @strawberry.mutation
    async def update_employee_role(
        self, info: Info, employee_id: strawberry.ID, role: ApplicationRole
    ) -> AdminEmployee:
        subject = await _admin_subject(info)
        try:
            return _admin_employee(
                await update_admin_employee_role(subject, str(employee_id), role.value)
            )
        except (EmployeeDomainError, EmployeeUnavailableError) as error:
            _raise_admin_error(error)

    @strawberry.mutation
    async def set_employee_active(
        self, info: Info, employee_id: strawberry.ID, active: bool
    ) -> AdminEmployee:
        subject = await _admin_subject(info)
        try:
            return _admin_employee(
                await update_admin_employee_active(subject, str(employee_id), active)
            )
        except (EmployeeDomainError, EmployeeUnavailableError) as error:
            _raise_admin_error(error)

    @strawberry.mutation
    async def reconcile_employee(self, info: Info, employee_id: strawberry.ID) -> AdminEmployee:
        subject = await _admin_subject(info)
        try:
            return _admin_employee(await reconcile_admin_employee(subject, str(employee_id)))
        except (EmployeeDomainError, EmployeeUnavailableError) as error:
            _raise_admin_error(error)


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[
        lambda: QueryDepthLimiter(max_depth=4),
        lambda: MaxAliasesLimiter(max_alias_count=10),
    ],
)
