"""Transaction contracts for future planning/extension producers, not public endpoints.

S10 never synthesizes assessments or escalation requests in production screens.
The owning future domain must call these in its authorized business transaction.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from .coordination_contracts import content, instant
from .models import DeliveryAssessment, DeliveryState, OwnerEscalation, Project
from .projects import ProjectError, identifier
from .transactions import lock_company


def producer_project(session, project_id):
    if not session.in_transaction():
        raise ProjectError("delivery_transaction_required")
    if session.new or session.dirty or session.deleted:
        raise ProjectError("delivery_contract_requires_clean_state")
    project = session.get(Project, identifier(project_id))
    if not project:
        raise ProjectError("project_not_found", 404)
    lock_company(session, project.issuer)
    session.expire_all()
    session.refresh(project)
    return project


def advance_schedule(session, project_id, expected_version):
    project = producer_project(session, project_id)
    state = session.get(DeliveryState, project.id)
    current = state.schedule_version if state else 0
    if type(expected_version) is not int or expected_version != current:
        raise ProjectError("stale_delivery_schedule")
    if not state:
        state = DeliveryState(project_id=project.id, schedule_version=0)
        session.add(state)
    state.schedule_version += 1
    session.flush()
    return state.schedule_version


def record_assessment(
    session, project_id, schedule_version, project_version, status, forecast_at, summary, now=None
):
    project = producer_project(session, project_id)
    state = session.get(DeliveryState, project.id)
    if (
        not state
        or type(schedule_version) is not int
        or type(project_version) is not int
        or state.schedule_version != schedule_version
        or project.version != project_version
    ):
        raise ProjectError("stale_delivery_schedule")
    if status not in {"ASSESSED", "UNASSESSED"} or (status == "ASSESSED") != (
        forecast_at is not None
    ):
        raise ProjectError("invalid_delivery_assessment", 400)
    clock = now or datetime.now(UTC)
    if clock.utcoffset() is None:
        raise ProjectError("invalid_delivery_assessment", 400)
    row = DeliveryAssessment(
        project_id=project.id,
        schedule_version=schedule_version,
        project_version=project_version,
        status=status,
        forecast_at=instant(forecast_at) if forecast_at is not None else None,
        summary=content(summary),
        created_at=clock,
        valid_until=clock + timedelta(minutes=10),
    )
    session.add(row)
    session.flush()
    return row


def open_escalation(session, project_id, source_request_id, assessment_id, reason, affected_team):
    project = producer_project(session, project_id)
    source_id = identifier(source_request_id)
    assessment = (
        session.get(DeliveryAssessment, identifier(assessment_id)) if assessment_id else None
    )
    if assessment_id and (not assessment or assessment.project_id != project.id):
        raise ProjectError("invalid_delivery_assessment", 400)
    reason, affected_team = content(reason), content(affected_team, 300)
    previous = session.scalar(
        select(OwnerEscalation).where(OwnerEscalation.source_request_id == source_id)
    )
    if previous:
        if (
            previous.project_id != project.id
            or previous.assessment_id != assessment_id
            or previous.reason != reason
            or previous.affected_team != affected_team
        ):
            raise ProjectError("delivery_request_conflict")
        return previous
    row = OwnerEscalation(
        project_id=project.id,
        source_request_id=source_id,
        assessment_id=assessment.id if assessment else None,
        reason=reason,
        affected_team=affected_team,
    )
    session.add(row)
    session.flush()
    return row


def refresh_escalation(session, project_id, escalation_id, expected_version, assessment_id):
    project = producer_project(session, project_id)
    row = session.scalar(
        select(OwnerEscalation).where(
            OwnerEscalation.id == identifier(escalation_id),
            OwnerEscalation.project_id == project.id,
        )
    )
    assessment = session.get(DeliveryAssessment, identifier(assessment_id))
    if (
        type(expected_version) is not int
        or not row
        or row.status != "PENDING"
        or row.version != expected_version
    ):
        raise ProjectError("stale_owner_escalation")
    if not assessment or assessment.project_id != project.id:
        raise ProjectError("invalid_delivery_assessment", 400)
    row.assessment_id = assessment.id
    row.version += 1
    session.flush()
    return row
