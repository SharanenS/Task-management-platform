"""Private, typed schedule projections and explicit preview/confirmation commands."""

import json
from dataclasses import asdict

import strawberry
from strawberry.types import Info

from .project_schema import ProjectRecord


@strawberry.type
class SchedulePoint:
    id: strawberry.ID
    requested_start: str | None
    duration: int | None
    prerequisites: list[strawberry.ID]
    effective_start: str | None
    starts_at: str | None
    due_at: str | None
    next_handoff: str | None
    adjusted: bool
    readiness: str
    issue: str | None


@strawberry.type
class ScheduleOverlap:
    task_id: strawberry.ID
    other_task_id: strawberry.ID


@strawberry.type
class ScheduleAnalysis:
    state: str
    forecast_at: str | None
    tasks: list[SchedulePoint]
    overlaps: list[ScheduleOverlap]
    capacity_checked: bool


def analysis(value):
    return ScheduleAnalysis(
        **{
            **value,
            "tasks": [SchedulePoint(**r) for r in value["tasks"]],
            "overlaps": [ScheduleOverlap(**r) for r in value["overlaps"]],
        }
    )


@strawberry.type
class ScheduleTask:
    title: str
    version: int
    status: str
    assignee_name: str | None
    plan: SchedulePoint
    original: SchedulePoint | None


@strawberry.type
class ScheduleHistory:
    id: strawberry.ID
    actor_name: str
    reason: str
    created_at: str
    before: ScheduleAnalysis
    after: ScheduleAnalysis


@strawberry.type
class ScheduleWorkspace:
    project: ProjectRecord
    can_plan: bool
    state: str | None
    forecast_at: str | None
    timezone: str
    calendar_number: int
    current_deadline: str
    tasks: list[ScheduleTask]
    overlaps: list[ScheduleOverlap]
    history: list[ScheduleHistory]


@strawberry.type
class SchedulePreview:
    preview_id: strawberry.ID
    valid_until: str
    before: ScheduleAnalysis
    after: ScheduleAnalysis
    calendar_number: int
    timezone: str
    approved_deadline: str
    exceeds_deadline: bool


@strawberry.input
class PreviewTaskScheduleInput:
    project_id: strawberry.ID
    task_id: strawberry.ID
    project_version: int
    version: int
    requested_start: str
    duration: int
    prerequisites: list[strawberry.ID]
    reason: str


@strawberry.input
class CommitTaskScheduleInput:
    project_id: strawberry.ID
    preview_id: strawberry.ID
    request_id: strawberry.ID
    confirm: bool


@strawberry.type
class ScheduleReceipt:
    project_version: int
    schedule_version: int


@strawberry.type
class ScheduleQuery:
    @strawberry.field
    async def project_schedule(self, info: Info, id: strawberry.ID) -> ScheduleWorkspace:
        value = await info.context.projects("schedule", {"id": str(id)})
        tasks = []
        for row in value["tasks"]:
            fields = {k: row[k] for k in ("title", "version", "status", "assignee_name")}
            point = {k: v for k, v in row.items() if k not in {*fields, "original"}}
            tasks.append(
                ScheduleTask(
                    **fields,
                    plan=SchedulePoint(**point),
                    original=SchedulePoint(**row["original"]) if row["original"] else None,
                )
            )
        history = [
            ScheduleHistory(
                **{
                    **r,
                    "before": analysis(json.loads(r["before"])),
                    "after": analysis(json.loads(r["after"])),
                }
            )
            for r in value["history"]
        ]
        return ScheduleWorkspace(
            **{
                **value,
                "project": ProjectRecord(**value["project"]),
                "tasks": tasks,
                "history": history,
                "overlaps": [ScheduleOverlap(**r) for r in value["overlaps"]],
            }
        )


@strawberry.type
class ScheduleMutation:
    @strawberry.mutation
    async def preview_task_schedule(
        self, info: Info, input: PreviewTaskScheduleInput
    ) -> SchedulePreview:
        value = await info.context.projects("schedule-preview", asdict(input))
        return SchedulePreview(
            **{**value, "before": analysis(value["before"]), "after": analysis(value["after"])}
        )

    @strawberry.mutation
    async def commit_task_schedule(
        self, info: Info, input: CommitTaskScheduleInput
    ) -> ScheduleReceipt:
        return ScheduleReceipt(**await info.context.projects("schedule-commit", asdict(input)))
