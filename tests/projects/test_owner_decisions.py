from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from project_work.delivery_inputs import (
    advance_schedule,
    open_escalation,
    record_assessment,
    refresh_escalation,
)
from project_work.models import OwnerDecision, OwnerEscalation, Project
from project_work.owner_decisions import OwnerDecisionService
from project_work.projects import ProjectError
from sqlalchemy import select

from .test_domain import create
from .test_domain import projects as projects
from .test_domain import setup as setup

NOW = datetime(2026, 11, 23, 9, tzinfo=UTC)


def arrange(projects, status="ASSESSED", forecast="2026-11-26T11:30:00Z"):
    work, sessions, owner, *_ = projects
    project, _ = create(work, owner)
    service = OwnerDecisionService(sessions, now=lambda: NOW)
    with sessions() as session, session.begin():
        version = advance_schedule(session, project["id"], 0)
        assessment = record_assessment(
            session,
            project["id"],
            version,
            project["version"],
            status,
            forecast if status == "ASSESSED" else None,
            "Dependency assessment fixture",
            now=NOW,
        )
        escalation = open_escalation(
            session,
            project["id"],
            str(uuid4()),
            assessment.id,
            "Additional time requested",
            "Project delivery team",
        )
        escalation_id = escalation.id
    return service, sessions, owner, project, escalation_id


def command(project, escalation_id, **changes):
    return {
        "project_id": project["id"],
        "escalation_id": escalation_id,
        "request_id": str(uuid4()),
        "version": 1,
        "project_version": project["version"],
        "outcome": "ACCEPT_FORECAST_LATE",
        "reason": "Accept a forecast late completion with recorded context",
        "affected_team": "Delivery team",
        "preview_id": None,
        "confirm": True,
        **changes,
    }


def test_no_task_inputs_means_unknown_forecast_and_empty_inbox(projects):
    work, sessions, owner, *_ = projects
    project, _ = create(work, owner)
    result = OwnerDecisionService(sessions, now=lambda: NOW).workspace(lambda: owner, project["id"])
    assert result["forecast_at"] is None and result["forecast_late"] is None
    assert result["actual_delivery_at"] is None
    assert result["forecast_state"] == "UNASSESSED"
    assert result["escalations"] == result["history"] == []
    assert result["current_deadline"] == project["approved_deadline"]


def test_accept_forecast_late_keeps_original_and_approved_deadlines(projects):
    service, sessions, owner, project, escalation = arrange(projects)
    request = command(project, escalation)
    result = service.decide(lambda: owner, request)
    assert result["outcome"] == "ACCEPT_FORECAST_LATE" and result["revised_deadline"] is None
    assert service.decide(lambda: owner, request) == result
    view = service.workspace(lambda: owner, project["id"])
    assert (
        view["project"]["approved_deadline"]
        == view["current_deadline"]
        == project["approved_deadline"]
    )
    assert view["actual_delivery_at"] is None
    assert len(view["history"]) == 1 and view["escalations"] == []
    with sessions() as session:
        assert session.get(OwnerEscalation, escalation).status == "DECIDED"
        assert len(session.scalars(select(OwnerDecision)).all()) == 1
    with pytest.raises(ProjectError, match="owner_request_conflict"):
        service.decide(lambda: owner, {**request, "reason": "Different reason"})


def test_revision_preview_preserves_baseline_and_records_new_commitment(projects):
    service, sessions, owner, project, escalation = arrange(projects)
    preview = service.preview(
        lambda: owner,
        {
            "project_id": project["id"],
            "escalation_id": escalation,
            "version": 1,
            "deadline_date": "2026-11-27",
        },
    )
    assert preview["original_deadline"] == project["approved_deadline"]
    decision = service.decide(
        lambda: owner,
        command(project, escalation, outcome="REVISE_DEADLINE", preview_id=preview["id"]),
    )
    view = service.workspace(lambda: owner, project["id"])
    assert view["current_deadline"] == preview["deadline_at"] == decision["revised_deadline"]
    assert view["project"]["approved_deadline"] == project["approved_deadline"]
    assert decision["previous_deadline"] == project["approved_deadline"]
    assert view["forecast_state"] == "STALE" and view["forecast_at"] is None
    with sessions() as session:
        assert session.get(Project, project["id"]).deadline_date == project["deadline_date"]


@pytest.mark.parametrize("outcome", ["REVISE_DEADLINE", "ACCEPT_FORECAST_LATE"])
def test_unknown_assessment_cannot_authorize_date_or_late_acceptance(projects, outcome):
    service, _, owner, project, escalation = arrange(projects, "UNASSESSED")
    with pytest.raises(ProjectError, match="owner_assessment_required"):
        service.decide(lambda: owner, command(project, escalation, outcome=outcome))


def test_unassessed_request_can_request_replan_without_claiming_approval(projects):
    service, _, owner, project, escalation = arrange(projects, "UNASSESSED")
    result = service.decide(lambda: owner, command(project, escalation, outcome="REQUEST_REPLAN"))
    assert result["outcome"] == "REQUEST_REPLAN" and result["revised_deadline"] is None


@pytest.mark.parametrize("change", ["expired", "schedule", "membership"])
def test_forecast_staleness_blocks_approval(projects, change):
    service, sessions, owner, project, escalation = arrange(projects)
    if change == "expired":
        service.now = lambda: NOW + timedelta(minutes=11)
    elif change == "schedule":
        with sessions() as session, session.begin():
            advance_schedule(session, project["id"], 1)
    else:
        with sessions() as session, session.begin():
            session.get(Project, project["id"]).version += 1
        project["version"] += 1
    with pytest.raises(ProjectError, match="owner_assessment_required"):
        service.decide(lambda: owner, command(project, escalation))


@pytest.mark.parametrize("role", ["EMPLOYEE", "HR", "MANAGER"])
def test_unrelated_actor_cannot_read_preview_or_decide(projects, role):
    service, _, owner, project, escalation = arrange(projects)
    stranger = replace(owner, account_id=str(uuid4()), role=role)
    for action in [
        lambda: service.workspace(lambda: stranger, project["id"]),
        lambda: service.preview(
            lambda: stranger,
            {
                "project_id": project["id"],
                "escalation_id": escalation,
                "version": 1,
                "deadline_date": "2026-11-27",
            },
        ),
        lambda: service.decide(lambda: stranger, command(project, escalation)),
    ]:
        with pytest.raises(ProjectError):
            action()
    with pytest.raises(ProjectError):
        service.workspace(lambda: replace(owner, issuer="https://foreign.invalid"), project["id"])


def test_admin_oversight_records_true_actor_and_does_not_impersonate_owner(projects):
    service, _, owner, project, escalation = arrange(projects)
    admin = replace(owner, role="ADMIN", account_id=str(uuid4()), display_name="Actual admin")
    result = service.decide(lambda: admin, command(project, escalation))
    assert result["actor_role"] == "ADMIN" and result["actor_name"] == "Actual admin"


def test_stale_or_unconfirmed_decision_never_changes_history(projects):
    service, sessions, owner, project, escalation = arrange(projects)
    for change in [
        {"confirm": False},
        {"version": True},
        {"project_version": 9},
        {"reason": ""},
        {"affected_team": ""},
    ]:
        with pytest.raises(ProjectError):
            service.decide(lambda: owner, command(project, escalation, **change))
    with sessions() as session:
        assert session.scalar(select(OwnerDecision)) is None


def test_changed_owner_after_lock_and_revoked_role_cannot_commit(projects, monkeypatch):
    service, sessions, owner, project, escalation = arrange(projects)

    def transfer(session, issuer):
        with sessions() as other:
            other.get(Project, project["id"]).owner_id = str(uuid4())
            other.commit()

    monkeypatch.setattr("project_work.owner_decisions.lock_company", transfer)
    with pytest.raises(ProjectError):
        service.decide(lambda: owner, command(project, escalation))
    with sessions() as session:
        assert session.scalar(select(OwnerDecision)) is None


def test_preview_is_bound_to_actor_and_current_calendar(projects):
    service, sessions, owner, project, escalation = arrange(projects)
    preview = service.preview(
        lambda: owner,
        {
            "project_id": project["id"],
            "escalation_id": escalation,
            "version": 1,
            "deadline_date": "2026-11-27",
        },
    )
    admin = replace(owner, role="ADMIN", account_id=str(uuid4()))
    with pytest.raises(ProjectError, match="stale_owner_preview"):
        service.decide(
            lambda: admin,
            command(project, escalation, outcome="REVISE_DEADLINE", preview_id=preview["id"]),
        )
    _, _, _, _, calendars, calendar_actor = projects
    from working_calendar.test_calendar import config

    value = config()
    value["holidays"].append({"date": "2099-12-31", "label": "New version"})
    new_preview = calendars.preview(calendar_actor, value)
    calendars.publish(
        calendar_actor,
        {"request_id": str(uuid4()), "preview_id": new_preview["preview_id"], "confirm": True},
    )
    with pytest.raises(ProjectError, match="stale_owner_preview"):
        service.decide(
            lambda: owner,
            command(project, escalation, outcome="REVISE_DEADLINE", preview_id=preview["id"]),
        )


def test_revision_does_not_erase_original_or_previous_overdue_history(projects):
    service, sessions, owner, project, escalation = arrange(projects)
    later = datetime(2026, 11, 25, 9, tzinfo=UTC)
    service.now = lambda: later
    with sessions() as session, session.begin():
        assessment = record_assessment(
            session,
            project["id"],
            1,
            project["version"],
            "ASSESSED",
            "2026-11-26T11:30:00Z",
            "Fresh reassessment",
            now=later,
        )
        refresh_escalation(session, project["id"], escalation, 1, assessment.id)
    preview = service.preview(
        lambda: owner,
        {
            "project_id": project["id"],
            "escalation_id": escalation,
            "version": 2,
            "deadline_date": "2026-11-27",
        },
    )
    decision = service.decide(
        lambda: owner,
        command(
            project, escalation, version=2, outcome="REVISE_DEADLINE", preview_id=preview["id"]
        ),
    )
    current = service.workspace(lambda: owner, project["id"])
    assert current["original_overdue"] and decision["previous_overdue"]
    assert not current["current_overdue"] and current["actual_delivery_at"] is None
    assert current["project"]["approved_deadline"] == project["approved_deadline"]


@pytest.mark.parametrize("date", ["2026-11-22", "2026-11-25", "bad-date"])
def test_revision_preview_rejects_nonworking_or_insufficient_dates(projects, date):
    service, _, owner, project, escalation = arrange(projects)
    with pytest.raises(ProjectError):
        service.preview(
            lambda: owner,
            {
                "project_id": project["id"],
                "escalation_id": escalation,
                "version": 1,
                "deadline_date": date,
            },
        )


def test_consecutive_requests_cannot_reuse_an_obsolete_assessment(projects):
    service, sessions, owner, project, first = arrange(projects)
    with sessions() as session, session.begin():
        assessment_id = session.get(OwnerEscalation, first).assessment_id
        second = open_escalation(
            session, project["id"], str(uuid4()), assessment_id, "Another request", "Another team"
        ).id
    service.decide(lambda: owner, command(project, first))
    with pytest.raises(ProjectError, match="stale_owner_escalation"):
        service.decide(lambda: owner, command(project, second))
    with pytest.raises(ProjectError, match="owner_assessment_required"):
        service.decide(
            lambda: owner, command(project, second, project_version=project["version"] + 1)
        )


def test_producer_contract_does_not_discard_pending_mutations(projects):
    _, sessions, _, project, _ = arrange(projects)
    with sessions() as session:
        with (
            pytest.raises(ProjectError, match="delivery_contract_requires_clean_state"),
            session.begin(),
        ):
            session.get(Project, project["id"]).name = "Unflushed mutation"
            advance_schedule(session, project["id"], 1)
    with sessions() as session:
        assert session.get(Project, project["id"]).name == project["name"]
