"""Typed task summaries; private details are nullable for authorized peers."""

from dataclasses import asdict

import strawberry
from strawberry.types import Info

from .project_schema import ProjectRecord


@strawberry.type
class TaskHistory:
    id: strawberry.ID
    action: str
    reason: str
    actor_name: str
    before: str
    after: str
    version: int
    created_at: str


@strawberry.type
class TaskDetails:
    instructions: str
    acceptance_criteria: str
    version: int
    assignee_id: strawberry.ID | None
    assigned_at: str | None
    history: list[TaskHistory]


@strawberry.type
class TaskRecord:
    id: strawberry.ID
    title: str
    status: str
    assignee_name: str | None
    details: TaskDetails | None


@strawberry.type
class TaskWorkspace:
    project: ProjectRecord
    can_plan: bool
    has_more: bool
    tasks: list[TaskRecord]


@strawberry.type
class TaskCandidate:
    account_id: strawberry.ID
    display_name: str


@strawberry.type
class TaskCandidates:
    candidates: list[TaskCandidate]
    has_more: bool


@strawberry.type
class TaskChangeReceipt:
    task_id: strawberry.ID
    version: int
    project_version: int


@strawberry.input
class ChangeTaskInput:
    project_id: strawberry.ID
    request_id: strawberry.ID
    project_version: int
    action: str
    task_id: strawberry.ID | None
    version: int
    title: str | None
    instructions: str | None
    acceptance_criteria: str | None
    assignee_id: strawberry.ID | None
    reason: str
    confirm: bool


@strawberry.type
class TaskQuery:
    @strawberry.field
    async def project_tasks(self, info: Info, id: strawberry.ID, page: int = 0) -> TaskWorkspace:
        value = await info.context.projects("tasks", {"id": str(id), "page": page})
        rows = []
        for row in value["tasks"]:
            details = row["details"]
            rows.append(
                TaskRecord(
                    **{
                        **row,
                        "details": TaskDetails(
                            **{**details, "history": [TaskHistory(**h) for h in details["history"]]}
                        )
                        if details
                        else None,
                    }
                )
            )
        return TaskWorkspace(
            project=ProjectRecord(**value["project"]),
            can_plan=value["can_plan"],
            has_more=value["has_more"],
            tasks=rows,
        )

    @strawberry.field
    async def task_candidates(self, info: Info, id: strawberry.ID, page: int = 0) -> TaskCandidates:
        value = await info.context.projects("task-candidates", {"id": str(id), "page": page})
        return TaskCandidates(
            candidates=[TaskCandidate(**v) for v in value["candidates"]], has_more=value["has_more"]
        )


@strawberry.type
class TaskMutation:
    @strawberry.mutation
    async def change_task(self, info: Info, input: ChangeTaskInput) -> TaskChangeReceipt:
        return TaskChangeReceipt(**await info.context.projects("task-change", asdict(input)))
