from enum import StrEnum

import strawberry
from graphql import GraphQLError
from strawberry.extensions import MaxAliasesLimiter, QueryDepthLimiter
from strawberry.types import Info

from app.auth import AuthenticationError, token_validator
from app.config import settings
from app.employee_client import (
    EmployeeForbiddenError,
    EmployeeUnavailableError,
    get_employee,
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


@strawberry.type
class Employee:
    id: strawberry.ID
    display_name: str
    email: str
    role: ApplicationRole


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


schema = strawberry.Schema(
    query=Query,
    extensions=[
        lambda: QueryDepthLimiter(max_depth=4),
        lambda: MaxAliasesLimiter(max_alias_count=10),
    ],
)
