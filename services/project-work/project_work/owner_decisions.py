"""Owner oversight: retain baselines, separate revisions and reject stale forecasts."""

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from .calendar import (
    TZDB_VERSION,
    CalendarError,
    day,
    local_boundary,
    normalize,
    timezone_rules,
    working_hours,
)
from .coordination import fingerprint
from .coordination_contracts import content
from .memberships import MembershipService, read_actor
from .models import (
    DeliveryAssessment,
    DeliveryState,
    OwnerDecision,
    OwnerDecisionPreview,
    OwnerEscalation,
)
from .projects import ProjectError, identifier, latest_calendar, project_view, utc
from .transactions import lock_company


def clock_value(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class OwnerDecisionService:
    def __init__(self, sessions, now=None):
        self.sessions = sessions
        self.now = now or (lambda: datetime.now(UTC))
        self.memberships = MembershipService(sessions)

    def project(self, session, authority, project_id):
        actor = read_actor(authority)
        if actor.role not in {"ADMIN", "MANAGER"}:
            raise ProjectError("owner_management_denied", 403)
        return actor, self.memberships.project(session, actor, project_id, management=True)

    def locked_project(self, session, authority, project_id):
        if session.new or session.dirty or session.deleted:
            raise ProjectError("delivery_contract_requires_clean_state")
        actor, project = self.project(session, authority, project_id)
        lock_company(session, actor.issuer)
        session.expire_all()
        current, project = self.project(session, authority, project_id)
        if current != actor:
            raise ProjectError("owner_authority_changed", 403)
        return actor, project

    def current_deadline(self, session, project):
        revision = session.scalar(
            select(OwnerDecision)
            .where(
                OwnerDecision.project_id == project.id, OwnerDecision.outcome == "REVISE_DEADLINE"
            )
            .order_by(OwnerDecision.project_version.desc())
            .limit(1)
        )
        return clock_value(revision.revised_deadline if revision else project.approved_deadline)

    def assessment(self, session, project, assessment_id):
        row = (
            session.scalar(
                select(DeliveryAssessment).where(
                    DeliveryAssessment.project_id == project.id,
                    DeliveryAssessment.id == assessment_id,
                )
            )
            if assessment_id
            else None
        )
        state = session.get(DeliveryState, project.id)
        current = bool(
            row
            and state
            and row.project_version == project.version
            and row.schedule_version == state.schedule_version
            and clock_value(row.created_at) <= self.now() < clock_value(row.valid_until)
        )
        return row, current

    def escalation(self, session, project, escalation_id):
        row = session.scalar(
            select(OwnerEscalation).where(
                OwnerEscalation.id == identifier(escalation_id),
                OwnerEscalation.project_id == project.id,
            )
        )
        if not row:
            raise ProjectError("owner_escalation_not_found", 404)
        return row

    def assessed(self, session, project, escalation):
        assessment, current = self.assessment(session, project, escalation.assessment_id)
        if not current or assessment.status != "ASSESSED" or not assessment.forecast_at:
            raise ProjectError("owner_assessment_required")
        if clock_value(assessment.forecast_at) <= self.current_deadline(session, project):
            raise ProjectError("owner_escalation_within_deadline")
        return assessment

    def workspace(self, authority, project_id, page=0):
        if type(page) is not int or not 0 <= page <= 10000:
            raise ProjectError("invalid_owner_request", 400)
        with self.sessions() as session:
            _, project = self.project(session, authority, project_id)
            latest = session.scalar(
                select(DeliveryAssessment)
                .where(DeliveryAssessment.project_id == project.id)
                .order_by(DeliveryAssessment.created_at.desc(), DeliveryAssessment.id)
                .limit(1)
            )
            assessment, current = self.assessment(session, project, latest.id if latest else None)
            deadline = self.current_deadline(session, project)
            escalation_rows = session.scalars(
                select(OwnerEscalation)
                .where(
                    OwnerEscalation.project_id == project.id, OwnerEscalation.status == "PENDING"
                )
                .order_by(OwnerEscalation.created_at, OwnerEscalation.id)
                .offset(page * 25)
                .limit(26)
            ).all()
            history = session.scalars(
                select(OwnerDecision)
                .where(OwnerDecision.project_id == project.id)
                .order_by(OwnerDecision.project_version.desc())
                .offset(page * 25)
                .limit(26)
            ).all()
            forecast = (
                clock_value(assessment.forecast_at) if current and assessment.forecast_at else None
            )
            return {
                "project": project_view(project),
                "current_deadline": deadline.isoformat(),
                "original_overdue": clock_value(project.approved_deadline) < self.now(),
                "current_overdue": deadline < self.now(),
                "forecast_at": forecast.isoformat() if forecast else None,
                "forecast_state": assessment.status
                if current
                else "STALE"
                if assessment
                else "UNASSESSED",
                "forecast_late": forecast > deadline if forecast else None,
                "actual_delivery_at": None,
                "escalations": [
                    self.escalation_view(session, project, row) for row in escalation_rows[:25]
                ],
                "history": [self.decision_view(row) for row in history[:25]],
                "has_more": len(escalation_rows) > 25 or len(history) > 25,
            }

    def escalation_view(self, session, project, row):
        assessment, current = self.assessment(session, project, row.assessment_id)
        return {
            "id": row.id,
            "source_request_id": row.source_request_id,
            "version": row.version,
            "reason": row.reason,
            "affected_team": row.affected_team,
            "assessment_state": assessment.status
            if current
            else "STALE"
            if assessment
            else "UNASSESSED",
            "forecast_at": utc(assessment.forecast_at)
            if assessment and assessment.forecast_at
            else None,
            "assessment_summary": assessment.summary if assessment else None,
            "created_at": utc(row.created_at),
        }

    def decision_view(self, row):
        return {
            "id": row.id,
            "escalation_id": row.escalation_id,
            "outcome": row.outcome,
            "actor_name": row.actor_name,
            "actor_role": row.actor_role,
            "actor_id": row.actor_id,
            "reason": row.reason,
            "affected_team": row.affected_team,
            "forecast_at": utc(row.forecast_at) if row.forecast_at else None,
            "assessment_state": row.assessment_state,
            "previous_deadline": utc(row.previous_deadline),
            "revised_deadline": utc(row.revised_deadline) if row.revised_deadline else None,
            "previous_overdue": row.previous_overdue,
            "project_version": row.project_version,
            "created_at": utc(row.created_at),
        }

    def preview(self, authority, value):
        if set(value) != {"project_id", "escalation_id", "version", "deadline_date"}:
            raise ProjectError("invalid_owner_request", 400)
        with self.sessions() as session, session.begin():
            actor, project = self.locked_project(session, authority, value["project_id"])
            escalation = self.escalation(session, project, value["escalation_id"])
            if (
                type(value["version"]) is not int
                or value["version"] != escalation.version
                or escalation.status != "PENDING"
            ):
                raise ProjectError("stale_owner_escalation")
            assessment = self.assessed(session, project, escalation)
            calendar = latest_calendar(session, actor.issuer)
            if not calendar or calendar.tzdb_version != TZDB_VERSION:
                raise ProjectError("owner_calendar_required")
            try:
                config = normalize(json.loads(calendar.config))
                target = day(value["deadline_date"])
                hours = working_hours(config, target)
                if not hours:
                    raise ProjectError("non_working_deadline", 400)
                due = local_boundary(target, hours["closes"], config["timezone"])
            except CalendarError as error:
                raise ProjectError(error.code, 400) from None
            if due < clock_value(assessment.forecast_at) or due <= self.now():
                raise ProjectError("owner_deadline_before_forecast", 400)
            if self.project(session, authority, project.id)[0] != actor:
                raise ProjectError("owner_authority_changed", 403)
            row = OwnerDecisionPreview(
                project_id=project.id,
                escalation_id=escalation.id,
                actor_id=actor.account_id,
                project_version=project.version,
                escalation_version=escalation.version,
                assessment_id=assessment.id,
                calendar_version_id=calendar.id,
                deadline_date=target.isoformat(),
                deadline_at=due,
                deadline_local=due.astimezone(timezone_rules(config["timezone"])).isoformat(),
                expires_at=min(
                    clock_value(assessment.valid_until), self.now() + timedelta(minutes=10)
                ),
            )
            session.add(row)
            session.flush()
            return {
                "id": row.id,
                "deadline_at": utc(row.deadline_at),
                "deadline_local": row.deadline_local,
                "original_deadline": utc(project.approved_deadline),
                "current_deadline": self.current_deadline(session, project).isoformat(),
                "forecast_at": utc(assessment.forecast_at),
                "calendar_number": calendar.number,
                "expires_at": utc(row.expires_at),
            }

    def decide(self, authority, value):
        with self.sessions() as session, session.begin():
            return self.decide_in_transaction(session, authority, value)

    def decide_in_transaction(self, session, authority, value):
        """Future extension mutations can share this exact transaction and lock."""
        if not session.in_transaction():
            raise ProjectError("delivery_transaction_required")
        required = {
            "project_id",
            "escalation_id",
            "request_id",
            "version",
            "project_version",
            "outcome",
            "reason",
            "affected_team",
            "preview_id",
            "confirm",
        }
        if set(value) != required or value["confirm"] is not True:
            raise ProjectError("invalid_owner_request", 400)
        if (
            type(value["version"]) is not int
            or value["version"] < 1
            or type(value["project_version"]) is not int
            or value["project_version"] < 1
            or value["outcome"] not in {"REVISE_DEADLINE", "ACCEPT_FORECAST_LATE", "REQUEST_REPLAN"}
        ):
            raise ProjectError("invalid_owner_request", 400)
        reason, team = content(value["reason"]), content(value["affected_team"], 300)
        request_id = identifier(value["request_id"])
        actor, project = self.locked_project(session, authority, value["project_id"])
        escalation = self.escalation(session, project, value["escalation_id"])
        digest = fingerprint(value)
        previous = session.scalar(
            select(OwnerDecision).where(OwnerDecision.request_id == request_id)
        )
        if previous:
            if (
                previous.project_id != project.id
                or previous.actor_id != actor.account_id
                or previous.request_hash != digest
            ):
                raise ProjectError("owner_request_conflict")
            return self.decision_view(previous)
        if (
            escalation.version != value["version"]
            or escalation.status != "PENDING"
            or project.version != value["project_version"]
        ):
            raise ProjectError("stale_owner_escalation")
        if value["outcome"] != "REQUEST_REPLAN":
            assessment = self.assessed(session, project, escalation)
            assessment_state = assessment.status
        else:
            assessment, current = self.assessment(session, project, escalation.assessment_id)
            assessment_state = (
                assessment.status if current else "STALE" if assessment else "UNASSESSED"
            )
        preview = None
        if value["outcome"] == "REVISE_DEADLINE":
            preview = session.scalar(
                select(OwnerDecisionPreview).where(
                    OwnerDecisionPreview.id == identifier(value["preview_id"]),
                    OwnerDecisionPreview.project_id == project.id,
                    OwnerDecisionPreview.escalation_id == escalation.id,
                )
            )
            calendar = latest_calendar(session, actor.issuer)
            if (
                not preview
                or preview.actor_id != actor.account_id
                or preview.project_version != project.version
                or preview.escalation_version != escalation.version
                or preview.assessment_id != assessment.id
                or clock_value(preview.expires_at) <= self.now()
                or not calendar
                or preview.calendar_version_id != calendar.id
                or calendar.tzdb_version != TZDB_VERSION
            ):
                raise ProjectError("stale_owner_preview")
            if clock_value(preview.deadline_at) < clock_value(assessment.forecast_at):
                raise ProjectError("owner_deadline_before_forecast")
        elif value["preview_id"] is not None:
            raise ProjectError("invalid_owner_request", 400)
        if self.project(session, authority, project.id)[0] != actor:
            raise ProjectError("owner_authority_changed", 403)
        prior = self.current_deadline(session, project)
        project.version += 1
        row = OwnerDecision(
            project_id=project.id,
            escalation_id=escalation.id,
            assessment_id=escalation.assessment_id,
            preview_id=preview.id if preview else None,
            request_id=request_id,
            request_hash=digest,
            actor_id=actor.account_id,
            actor_name=actor.display_name,
            actor_role=actor.role,
            outcome=value["outcome"],
            reason=reason,
            affected_team=team,
            forecast_at=assessment.forecast_at if assessment else None,
            assessment_state=assessment_state,
            previous_deadline=prior,
            revised_deadline=preview.deadline_at if preview else None,
            previous_overdue=prior < self.now(),
            project_version=project.version,
            created_at=self.now(),
        )
        escalation.status = "DECIDED"
        escalation.version += 1
        session.add(row)
        session.flush()
        return self.decision_view(row)
