"""Project contracts never accept creator/owner authority from the browser."""

from dataclasses import asdict

import strawberry
from strawberry.types import Info


@strawberry.type
class ProjectRecord:
    id: strawberry.ID
    name: str
    objectives: str
    creator_id: strawberry.ID
    creator_name: str
    owner_id: strawberry.ID
    owner_name: str
    deadline_date: str
    approved_deadline: str
    deadline_local: str
    calendar_version_id: strawberry.ID
    calendar_number: int
    timezone: str
    tzdb_version: str
    created_at: str
    version: int


@strawberry.type
class ProjectCalendarReference:
    id: strawberry.ID
    number: int
    timezone: str
    tzdb_version: str


@strawberry.type
class ProjectWorkspace:
    projects: list[ProjectRecord]
    has_more: bool
    calendar: ProjectCalendarReference | None


@strawberry.type
class ProjectCreationPreview:
    preview_id: strawberry.ID
    name: str
    objectives: str
    deadline_date: str
    approved_deadline: str
    deadline_local: str
    calendar_number: int
    timezone: str
    tzdb_version: str
    expires_at: str
    past_deadline: bool


@strawberry.input
class ProjectPreviewInput:
    name: str
    objectives: str
    deadline_date: str


@strawberry.input
class CreateProjectInput:
    request_id: strawberry.ID
    preview_id: strawberry.ID
    confirm: bool


@strawberry.type
class ProjectMember:
    id: strawberry.ID
    account_id: strawberry.ID | None
    display_name: str
    responsibility: str
    duties: str | None
    active: bool


@strawberry.type
class ProjectMembershipHistory:
    id: strawberry.ID
    actor_id: strawberry.ID
    target_id: strawberry.ID
    action: str
    before: str
    after: str
    project_version: int
    created_at: str


@strawberry.type
class ProjectMembershipWorkspace:
    project: ProjectRecord
    can_manage: bool
    responsibility: str
    members: list[ProjectMember]
    history: list[ProjectMembershipHistory]


@strawberry.type
class ProjectCandidate:
    account_id: strawberry.ID
    display_name: str
    role: str
    active: bool


@strawberry.type
class ProjectCandidates:
    candidates: list[ProjectCandidate]
    has_more: bool


@strawberry.input
class ChangeProjectMembershipInput:
    project_id: strawberry.ID
    request_id: strawberry.ID
    version: int
    account_id: strawberry.ID
    action: str
    confirm: bool
    responsibility: str = "CONTRIBUTOR"
    duties: str = ""


@strawberry.type
class ProjectMembershipResult:
    project_id: strawberry.ID
    version: int
    change_id: strawberry.ID


@strawberry.type
class ProjectQuery:
    @strawberry.field
    async def project_membership(self, info: Info, id: strawberry.ID) -> ProjectMembershipWorkspace:
        value = await info.context.projects("members", {"id": str(id)})
        return ProjectMembershipWorkspace(
            project=ProjectRecord(**value["project"]),
            can_manage=value["can_manage"],
            responsibility=value["responsibility"],
            members=[ProjectMember(**r) for r in value["members"]],
            history=[ProjectMembershipHistory(**r) for r in value["history"]],
        )

    @strawberry.field
    async def project_candidates(
        self, info: Info, id: strawberry.ID, page: int = 0, search: str = ""
    ) -> ProjectCandidates:
        value = await info.context.projects(
            "candidates", {"id": str(id), "page": page, "search": search}
        )
        return ProjectCandidates(
            candidates=[ProjectCandidate(**r) for r in value["candidates"]],
            has_more=value["has_more"],
        )

    @strawberry.field
    async def project_workspace(
        self, info: Info, page: int = 0, search: str = ""
    ) -> ProjectWorkspace:
        value = await info.context.projects("list", {"page": page, "search": search})
        return ProjectWorkspace(
            projects=[ProjectRecord(**r) for r in value["projects"]],
            has_more=value["has_more"],
            calendar=ProjectCalendarReference(**value["calendar"]) if value["calendar"] else None,
        )

    @strawberry.field
    async def project(self, info: Info, id: strawberry.ID) -> ProjectRecord:
        return ProjectRecord(**await info.context.projects("detail", {"id": str(id)}))


@strawberry.type
class ProjectMutation:
    @strawberry.mutation
    async def change_project_membership(
        self, info: Info, input: ChangeProjectMembershipInput
    ) -> ProjectMembershipResult:
        return ProjectMembershipResult(
            **await info.context.projects("membership-change", asdict(input))
        )

    @strawberry.mutation
    async def preview_project(
        self, info: Info, input: ProjectPreviewInput
    ) -> ProjectCreationPreview:
        return ProjectCreationPreview(**await info.context.projects("preview", asdict(input)))

    @strawberry.mutation
    async def create_project(self, info: Info, input: CreateProjectInput) -> ProjectRecord:
        return ProjectRecord(**await info.context.projects("create", asdict(input)))
