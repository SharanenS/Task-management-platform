"""Typed owner oversight API; task-produced inputs have no public write operation."""

from dataclasses import asdict

import strawberry
from strawberry.types import Info

from .project_schema import ProjectRecord


@strawberry.type
class OwnerEscalation:
    id: strawberry.ID
    source_request_id: strawberry.ID
    version: int
    reason: str
    affected_team: str
    assessment_state: str
    forecast_at: str | None
    assessment_summary: str | None
    created_at: str


@strawberry.type
class OwnerDecision:
    id: strawberry.ID
    escalation_id: strawberry.ID
    outcome: str
    actor_id: strawberry.ID
    actor_name: str
    actor_role: str
    reason: str
    affected_team: str
    forecast_at: str | None
    assessment_state: str
    previous_deadline: str
    revised_deadline: str | None
    previous_overdue: bool
    project_version: int
    created_at: str


@strawberry.type
class OwnerOversight:
    project: ProjectRecord
    current_deadline: str
    original_overdue: bool
    current_overdue: bool
    forecast_at: str | None
    forecast_state: str
    forecast_late: bool | None
    actual_delivery_at: str | None
    escalations: list[OwnerEscalation]
    history: list[OwnerDecision]
    has_more: bool


@strawberry.type
class OwnerDecisionPreview:
    id: strawberry.ID
    deadline_at: str
    deadline_local: str
    original_deadline: str
    current_deadline: str
    forecast_at: str
    calendar_number: int
    expires_at: str


@strawberry.type
class ReviewFallback:
    id: strawberry.ID
    leader_id: strawberry.ID | None
    leader_name: str | None
    scope: str
    reason: str
    actor_id: strawberry.ID
    actor_name: str
    starts_at: str
    ends_at: str
    created_at: str
    active: bool
    revoked_at: str | None
    revoked_by: strawberry.ID | None
    revocation_reason: str | None


@strawberry.type
class ReviewFallbacks:
    can_record: bool
    leader_id: strawberry.ID | None
    leader_name: str | None
    records: list[ReviewFallback]
    has_more: bool


@strawberry.input
class PreviewOwnerDeadlineInput:
    project_id: strawberry.ID
    escalation_id: strawberry.ID
    version: int
    deadline_date: str


@strawberry.input
class RecordOwnerDecisionInput:
    project_id: strawberry.ID
    escalation_id: strawberry.ID
    request_id: strawberry.ID
    version: int
    project_version: int
    outcome: str
    reason: str
    affected_team: str
    confirm: bool
    preview_id: strawberry.ID | None = None


@strawberry.input
class RecordReviewFallbackInput:
    project_id: strawberry.ID
    request_id: strawberry.ID
    project_version: int
    scope: str
    reason: str
    starts_at: str
    ends_at: str
    confirm: bool
    leader_id: strawberry.ID | None = None


@strawberry.input
class RevokeReviewFallbackInput:
    project_id: strawberry.ID
    record_id: strawberry.ID
    request_id: strawberry.ID
    reason: str
    confirm: bool


@strawberry.type
class OwnerQuery:
    @strawberry.field
    async def owner_oversight(self, info: Info, id: strawberry.ID, page: int = 0) -> OwnerOversight:
        value = await info.context.projects("owner-workspace", {"id": str(id), "page": page})
        return OwnerOversight(
            **{
                **value,
                "project": ProjectRecord(**value["project"]),
                "escalations": [OwnerEscalation(**r) for r in value["escalations"]],
                "history": [OwnerDecision(**r) for r in value["history"]],
            }
        )

    @strawberry.field
    async def review_fallbacks(
        self, info: Info, id: strawberry.ID, page: int = 0
    ) -> ReviewFallbacks:
        value = await info.context.projects("owner-fallbacks", {"id": str(id), "page": page})
        return ReviewFallbacks(
            **{**value, "records": [ReviewFallback(**r) for r in value["records"]]}
        )


@strawberry.type
class OwnerMutation:
    @strawberry.mutation
    async def preview_owner_deadline(
        self, info: Info, input: PreviewOwnerDeadlineInput
    ) -> OwnerDecisionPreview:
        return OwnerDecisionPreview(**await info.context.projects("owner-preview", asdict(input)))

    @strawberry.mutation
    async def record_owner_decision(
        self, info: Info, input: RecordOwnerDecisionInput
    ) -> OwnerDecision:
        return OwnerDecision(**await info.context.projects("owner-decide", asdict(input)))

    @strawberry.mutation
    async def record_review_fallback(
        self, info: Info, input: RecordReviewFallbackInput
    ) -> ReviewFallback:
        return ReviewFallback(**await info.context.projects("owner-fallback-create", asdict(input)))

    @strawberry.mutation
    async def revoke_review_fallback(
        self, info: Info, input: RevokeReviewFallbackInput
    ) -> ReviewFallback:
        return ReviewFallback(**await info.context.projects("owner-fallback-revoke", asdict(input)))
