"""Private completion queue and assignee actions; all authority stays in project-work."""

from dataclasses import asdict

import strawberry
from strawberry.types import Info

from .project_schema import ProjectRecord
from .task_schema import TaskChangeReceipt


@strawberry.type
class CompletionDecision:
    actor_name: str
    outcome: str
    feedback: str
    self_approval: bool
    fallback_id: strawberry.ID | None
    decided_at: str


@strawberry.type
class CompletionSubmission:
    id: strawberry.ID
    submitter_name: str
    submitted_at: str
    version: int
    summary: str
    snapshot: str
    pending: bool
    decision: CompletionDecision | None


@strawberry.type
class WorkUpdate:
    id: strawberry.ID
    action: str
    note: str
    actor_name: str
    created_at: str
    progress: int
    blocker: str | None
    status: str


@strawberry.type
class ReviewTask:
    id: strawberry.ID
    title: str
    status: str
    version: int
    own: bool
    can_act: bool
    can_review: bool
    instructions: str
    acceptance_criteria: str
    assignee_name: str | None
    progress: int
    blocker: str | None
    started_at: str | None
    completed_at: str | None
    work_history: list[WorkUpdate]
    submissions: list[CompletionSubmission]


@strawberry.type
class CompletionWorkspace:
    project: ProjectRecord
    is_leader: bool
    can_review: bool
    fallback_id: strawberry.ID | None
    has_more: bool
    tasks: list[ReviewTask]


@strawberry.input
class ExecuteTaskInput:
    project_id: strawberry.ID
    task_id: strawberry.ID
    project_version: int
    version: int
    request_id: strawberry.ID
    action: str
    note: str
    progress: int
    blocker: str | None
    confirm: bool


@strawberry.input
class ReviewCompletionInput:
    project_id: strawberry.ID
    task_id: strawberry.ID
    submission_id: strawberry.ID
    project_version: int
    version: int
    request_id: strawberry.ID
    outcome: str
    feedback: str
    self_confirm: bool
    confirm: bool


@strawberry.type
class CompletionQuery:
    @strawberry.field
    async def project_reviews(
        self, info: Info, id: strawberry.ID, page: int = 0
    ) -> CompletionWorkspace:
        value = await info.context.projects("reviews", {"id": str(id), "page": page})
        rows = []
        for task in value["tasks"]:
            submissions = [
                CompletionSubmission(
                    **{
                        **s,
                        "decision": CompletionDecision(**s["decision"]) if s["decision"] else None,
                    }
                )
                for s in task["submissions"]
            ]
            rows.append(
                ReviewTask(
                    **{
                        **task,
                        "submissions": submissions,
                        "work_history": [WorkUpdate(**r) for r in task["work_history"]],
                    }
                )
            )
        return CompletionWorkspace(
            **{**value, "project": ProjectRecord(**value["project"]), "tasks": rows}
        )


@strawberry.type
class CompletionMutation:
    @strawberry.mutation
    async def execute_task(self, info: Info, input: ExecuteTaskInput) -> TaskChangeReceipt:
        return TaskChangeReceipt(**await info.context.projects("review-execute", asdict(input)))

    @strawberry.mutation
    async def review_completion(
        self, info: Info, input: ReviewCompletionInput
    ) -> TaskChangeReceipt:
        return TaskChangeReceipt(**await info.context.projects("review-decide", asdict(input)))
