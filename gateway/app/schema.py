from datetime import datetime
from enum import StrEnum
from typing import NoReturn

import strawberry
from graphql import GraphQLError
from strawberry.extensions import MaxAliasesLimiter, QueryDepthLimiter
from strawberry.types import Info

from app.auth import AuthenticationError, token_validator
from app.config import settings
from app.employee_client import EligibleEmployee as EligibleEmployeeProfile
from app.employee_client import (
    EmployeeAdminProfile,
    EmployeeDomainError,
    EmployeeForbiddenError,
    EmployeeProfile,
    EmployeeUnavailableError,
    get_admin_employee,
    get_employee,
    list_admin_employees,
    list_eligible_employees,
    provision_admin_employee,
    reconcile_admin_employee,
    resolve_employee_references,
    update_admin_employee_active,
    update_admin_employee_role,
    validate_eligible_employee,
)
from app.work_client import (
    WorkDomainError,
    WorkMembership,
    WorkProject,
    WorkUnavailableError,
)
from app.work_client import (
    add_member as work_add_member,
)
from app.work_client import (
    change_member_role as work_change_member_role,
)
from app.work_client import (
    change_status as work_change_status,
)
from app.work_client import (
    create_project as work_create_project,
)
from app.work_client import (
    get_project as work_get_project,
)
from app.work_client import (
    list_projects as work_list_projects,
)
from app.work_client import (
    remove_member as work_remove_member,
)
from app.work_client import (
    update_project as work_update_project,
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


@strawberry.enum
class ProjectStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


@strawberry.enum
class ProjectRole(StrEnum):
    PROJECT_MANAGER = "PROJECT_MANAGER"
    CONTRIBUTOR = "CONTRIBUTOR"


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


@strawberry.type
class EligibleEmployee:
    id: strawberry.ID
    display_name: str
    email: str


@strawberry.type
class EligibleEmployeeConnection:
    nodes: list[EligibleEmployee]
    page_info: PageInfo


@strawberry.type
class ProjectMembership:
    id: strawberry.ID
    employee_id: strawberry.ID
    role: ProjectRole
    created_at: datetime
    display_name: str | None
    email: str | None


@strawberry.type
class Project:
    id: strawberry.ID
    key: str
    name: str
    description: str | None
    status: ProjectStatus
    creator_employee_id: strawberry.ID
    version: int
    created_at: datetime
    updated_at: datetime
    memberships: list[ProjectMembership]


@strawberry.type
class ProjectConnection:
    nodes: list[Project]
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


@strawberry.input
class CreateProjectInput:
    key: str
    name: str
    description: str | None = None


@strawberry.input
class UpdateProjectInput:
    name: str
    description: str | None
    expected_version: int


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


def _project_membership(
    member: WorkMembership, profiles: dict[str, EligibleEmployeeProfile]
) -> ProjectMembership:
    profile = profiles.get(member.employee_id)
    return ProjectMembership(
        id=strawberry.ID(member.id),
        employee_id=strawberry.ID(member.employee_id),
        role=ProjectRole(member.role),
        created_at=datetime.fromisoformat(member.created_at),
        display_name=profile.display_name if profile else None,
        email=profile.email if profile else None,
    )


def _project(
    value: WorkProject, profiles: dict[str, EligibleEmployeeProfile] | None = None
) -> Project:
    profiles = profiles or {}
    return Project(
        id=strawberry.ID(value.id),
        key=value.key,
        name=value.name,
        description=value.description,
        status=ProjectStatus(value.status),
        creator_employee_id=strawberry.ID(value.creator_employee_id),
        version=value.version,
        created_at=datetime.fromisoformat(value.created_at),
        updated_at=datetime.fromisoformat(value.updated_at),
        memberships=[_project_membership(member, profiles) for member in value.memberships],
    )


async def _enriched_projects(subject: str, values: list[WorkProject]) -> list[Project]:
    employee_ids = list(
        dict.fromkeys(member.employee_id for project in values for member in project.memberships)
    )
    profiles = {
        profile.id: profile
        for profile in (
            await resolve_employee_references(subject, employee_ids) if employee_ids else []
        )
    }
    return [_project(value, profiles) for value in values]


async def _enriched_project(subject: str, value: WorkProject) -> Project:
    return (await _enriched_projects(subject, [value]))[0]


async def _project_actor(info: Info) -> tuple[str, EmployeeProfile]:
    try:
        identity = token_validator.validate(info.context["authorization"])
    except AuthenticationError as error:
        raise GraphQLError(
            "Authentication is required.", extensions={"code": "UNAUTHENTICATED"}
        ) from error
    try:
        return identity.subject, await get_employee(identity.subject)
    except EmployeeForbiddenError as error:
        raise GraphQLError(
            "Project access is not available for this account.", extensions={"code": "FORBIDDEN"}
        ) from error
    except EmployeeUnavailableError as error:
        raise GraphQLError(
            "Project access is temporarily unavailable.",
            extensions={"code": "SERVICE_UNAVAILABLE"},
        ) from error


def _raise_project_error(error: Exception) -> NoReturn:
    if isinstance(error, WorkDomainError):
        raise GraphQLError(error.message, extensions={"code": error.code}) from error
    if isinstance(error, (WorkUnavailableError, EmployeeUnavailableError)):
        raise GraphQLError(
            "Project management is temporarily unavailable.",
            extensions={"code": "SERVICE_UNAVAILABLE"},
        ) from error
    if isinstance(error, EmployeeDomainError):
        raise GraphQLError(error.message, extensions={"code": error.code}) from error
    raise error


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

    @strawberry.field
    async def projects(
        self,
        info: Info,
        first: int = 20,
        after: str | None = None,
        search: str | None = None,
        status: ProjectStatus | None = None,
    ) -> ProjectConnection:
        subject, actor = await _project_actor(info)
        try:
            page = await work_list_projects(
                actor,
                first=first,
                after=after,
                search=search,
                status=status.value if status else None,
            )
            return ProjectConnection(
                nodes=await _enriched_projects(subject, page.items),
                page_info=PageInfo(
                    has_next_page=page.has_next_page,
                    end_cursor=page.next_cursor,
                ),
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.field
    async def project(self, info: Info, id: strawberry.ID) -> Project:
        subject, actor = await _project_actor(info)
        try:
            return await _enriched_project(subject, await work_get_project(actor, str(id)))
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.field
    async def eligible_project_members(
        self,
        info: Info,
        first: int = 20,
        after: str | None = None,
        search: str | None = None,
    ) -> EligibleEmployeeConnection:
        subject, actor = await _project_actor(info)
        if actor.role not in {"ADMIN", "MANAGER"}:
            raise GraphQLError(
                "Project membership lookup is not permitted.", extensions={"code": "FORBIDDEN"}
            )
        try:
            page = await list_eligible_employees(subject, first=first, after=after, search=search)
            return EligibleEmployeeConnection(
                nodes=[
                    EligibleEmployee(
                        id=strawberry.ID(item.id),
                        display_name=item.display_name,
                        email=item.email,
                    )
                    for item in page.items
                ],
                page_info=PageInfo(
                    has_next_page=page.has_next_page,
                    end_cursor=page.next_cursor,
                ),
            )
        except (EmployeeDomainError, EmployeeUnavailableError) as error:
            _raise_project_error(error)


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

    @strawberry.mutation
    async def create_project(self, info: Info, input: CreateProjectInput) -> Project:
        subject, actor = await _project_actor(info)
        if actor.role not in {"ADMIN", "MANAGER"}:
            raise GraphQLError(
                "Project creation is not permitted.", extensions={"code": "FORBIDDEN"}
            )
        try:
            return await _enriched_project(
                subject,
                await work_create_project(
                    actor,
                    {"key": input.key, "name": input.name, "description": input.description},
                ),
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.mutation
    async def update_project(
        self, info: Info, project_id: strawberry.ID, input: UpdateProjectInput
    ) -> Project:
        subject, actor = await _project_actor(info)
        try:
            return await _enriched_project(
                subject,
                await work_update_project(
                    actor,
                    str(project_id),
                    {
                        "name": input.name,
                        "description": input.description,
                        "expected_version": input.expected_version,
                    },
                ),
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.mutation
    async def set_project_status(
        self,
        info: Info,
        project_id: strawberry.ID,
        status: ProjectStatus,
        expected_version: int,
    ) -> Project:
        subject, actor = await _project_actor(info)
        try:
            return await _enriched_project(
                subject,
                await work_change_status(
                    actor,
                    str(project_id),
                    {"status": status.value, "expected_version": expected_version},
                ),
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.mutation
    async def add_project_member(
        self,
        info: Info,
        project_id: strawberry.ID,
        employee_id: strawberry.ID,
        role: ProjectRole,
    ) -> Project:
        subject, actor = await _project_actor(info)
        try:
            await validate_eligible_employee(subject, str(employee_id))
            return await _enriched_project(
                subject,
                await work_add_member(
                    actor,
                    str(project_id),
                    {"employee_id": str(employee_id), "role": role.value},
                ),
            )
        except (
            EmployeeDomainError,
            EmployeeUnavailableError,
            WorkDomainError,
            WorkUnavailableError,
        ) as error:
            _raise_project_error(error)

    @strawberry.mutation
    async def update_project_member_role(
        self,
        info: Info,
        project_id: strawberry.ID,
        employee_id: strawberry.ID,
        role: ProjectRole,
    ) -> Project:
        subject, actor = await _project_actor(info)
        try:
            return await _enriched_project(
                subject,
                await work_change_member_role(actor, str(project_id), str(employee_id), role.value),
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.mutation
    async def remove_project_member(
        self, info: Info, project_id: strawberry.ID, employee_id: strawberry.ID
    ) -> Project:
        subject, actor = await _project_actor(info)
        try:
            return await _enriched_project(
                subject,
                await work_remove_member(actor, str(project_id), str(employee_id)),
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[
        lambda: QueryDepthLimiter(max_depth=4),
        lambda: MaxAliasesLimiter(max_alias_count=10),
    ],
)
