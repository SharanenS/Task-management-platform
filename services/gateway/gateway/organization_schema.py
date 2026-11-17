"""Administrator organization contracts over the shared people-service authority."""

from dataclasses import asdict

import strawberry
from strawberry.types import Info


@strawberry.type
class OrganizationUnit:
    id: strawberry.ID
    name: str
    active: bool
    version: int


@strawberry.type
class EmployeeChoice:
    id: strawberry.ID
    display_name: str


@strawberry.type
class AvailableAccount:
    id: strawberry.ID
    company_role: str


@strawberry.type
class ManagedEmployee:
    id: strawberry.ID
    display_name: str
    active: bool
    version: int
    account_id: strawberry.ID | None
    company_role: str
    department_id: strawberry.ID | None
    job_title_id: strawberry.ID | None
    manager_id: strawberry.ID | None


@strawberry.type
class OrganizationHistory:
    id: strawberry.ID
    action: str
    entity_kind: str
    entity_name: str
    actor_name: str
    created_at: str


@strawberry.type
class OrganizationWorkspace:
    departments: list[OrganizationUnit]
    job_titles: list[OrganizationUnit]
    employees: list[ManagedEmployee]
    has_more: bool
    manager_options: list[EmployeeChoice]
    unlinked_employees: list[EmployeeChoice]
    available_accounts: list[AvailableAccount]
    history: list[OrganizationHistory]


@strawberry.type
class OrganizationChangeResult:
    entity_id: strawberry.ID
    state: str


@strawberry.input
class OrganizationChangeInput:
    request_id: strawberry.ID
    action: str
    entity_id: strawberry.ID | None = None
    kind: str | None = None
    name: str | None = None
    version: int | None = None
    active: bool | None = None
    department_id: strawberry.ID | None = None
    job_title_id: strawberry.ID | None = None
    manager_id: strawberry.ID | None = None
    account_id: strawberry.ID | None = None


@strawberry.type
class OrganizationQuery:
    @strawberry.field
    async def organization_workspace(
        self, info: Info, page: int = 0, search: str = ""
    ) -> OrganizationWorkspace:
        value = await info.context.organization("list", {"page": page, "search": search})
        return OrganizationWorkspace(
            departments=[OrganizationUnit(**d) for d in value["departments"]],
            job_titles=[OrganizationUnit(**t) for t in value["job_titles"]],
            employees=[ManagedEmployee(**e) for e in value["employees"]],
            has_more=value["has_more"],
            manager_options=[EmployeeChoice(**e) for e in value["manager_options"]],
            unlinked_employees=[EmployeeChoice(**e) for e in value["unlinked_employees"]],
            available_accounts=[AvailableAccount(**a) for a in value["available_accounts"]],
            history=[OrganizationHistory(**h) for h in value["history"]],
        )


@strawberry.type
class OrganizationMutation:
    @strawberry.mutation
    async def change_organization(
        self, info: Info, input: OrganizationChangeInput
    ) -> OrganizationChangeResult:
        return OrganizationChangeResult(**await info.context.organization("change", asdict(input)))
