from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from project_work.coordination import CoordinationService
from project_work.coordination_contracts import response_contract
from project_work.memberships import MembershipService
from project_work.models import CoordinationFollowUp, CoordinationRecord, Project, ProjectMember
from project_work.projects import ProjectError
from sqlalchemy import select

from .test_domain import create
from .test_domain import projects as projects
from .test_domain import setup as setup
from .test_memberships import appointment, eligible


def request(project, target, **changes):
    return {
        "project_id": project["id"],
        "request_id": str(uuid4()),
        "kind": "UPDATE",
        "topic": "Delivery check-in",
        "details": "Provide progress, blockers and next steps.",
        "due_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        "location": "",
        "acknowledgement_required": True,
        "recipients": [target],
        "confirm": True,
        **changes,
    }


def arrange(projects):
    work, sessions, owner, *_ = projects
    project, _ = create(work, owner)
    target = str(uuid4())
    MembershipService(sessions).change(lambda: owner, eligible, appointment(project, target))
    return CoordinationService(sessions), sessions, owner, project, target


@pytest.mark.parametrize("kind", ["UPDATE", "MEETING", "CHECK_IN"])
def test_creation_replay_and_pending_state_are_honest(projects, kind):
    service, sessions, owner, project, target = arrange(projects)
    value = request(project, target, kind=kind, location="Cabin 2" if kind != "UPDATE" else "")
    result = service.create(lambda: owner, eligible, value)
    assert service.create(lambda: owner, eligible, value) == result
    assert result["recipients"][0]["response_state"] == "PENDING"
    assert result["recipients"][0]["acknowledgement"] == "PENDING"
    assert result["follow_ups"] == [] and not result["overdue"]
    assert service.workspace(lambda: owner, project["id"])["records"] == [result]
    with sessions() as s:
        assert len(s.scalars(select(CoordinationRecord)).all()) == 1
    with pytest.raises(ProjectError, match="coordination_request_conflict"):
        service.create(lambda: owner, eligible, {**value, "topic": "Different"})


@pytest.mark.parametrize("role", ["EMPLOYEE", "HR", "MANAGER"])
def test_unrelated_roles_cannot_read_create_or_follow_up(projects, role):
    service, _, owner, project, target = arrange(projects)
    stranger = replace(owner, role=role, account_id=target if role == "EMPLOYEE" else str(uuid4()))
    called = []
    with pytest.raises(ProjectError):
        service.create(lambda: stranger, lambda t: called.append(t), request(project, target))
    with pytest.raises(ProjectError):
        service.workspace(lambda: stranger, project["id"])
    assert called == []


@pytest.mark.parametrize(
    "change", [{"active": False}, {"role": "HR"}, {"account_id": str(uuid4())}]
)
def test_current_people_eligibility_is_required(projects, change):
    service, sessions, owner, project, target = arrange(projects)
    with pytest.raises(ProjectError, match="coordination_recipient_ineligible"):
        service.create(lambda: owner, lambda t: {**eligible(t), **change}, request(project, target))
    with sessions() as s:
        assert s.scalar(select(CoordinationRecord)) is None


def test_revoked_appointment_and_cross_issuer_are_rejected(projects):
    service, sessions, owner, project, target = arrange(projects)
    with sessions() as s:
        s.scalar(select(ProjectMember)).active = False
        s.commit()
    with pytest.raises(ProjectError, match="coordination_recipient_ineligible"):
        service.create(lambda: owner, eligible, request(project, target))
    with pytest.raises(ProjectError):
        service.workspace(lambda: replace(owner, issuer="https://foreign.invalid"), project["id"])


def test_follow_up_retains_original_due_date_and_checks_version_and_replay(projects):
    service, sessions, owner, project, target = arrange(projects)
    record = service.create(lambda: owner, eligible, request(project, target))
    value = {
        "project_id": project["id"],
        "record_id": record["id"],
        "request_id": str(uuid4()),
        "version": 1,
        "note": "Review outstanding response",
        "next_follow_up_at": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
        "confirm": True,
    }
    updated = service.follow_up(lambda: owner, value)
    assert updated["version"] == 2 and updated["due_at"] == record["due_at"]
    assert service.follow_up(lambda: owner, value) == updated
    with pytest.raises(ProjectError, match="coordination_stale"):
        service.follow_up(lambda: owner, {**value, "request_id": str(uuid4())})
    with sessions() as s:
        assert len(s.scalars(select(CoordinationFollowUp)).all()) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"confirm": False},
        {"topic": ""},
        {"due_at": "2028-01-01T10:00:00"},
        {"due_at": "2020-01-01T10:00:00Z"},
        {"recipients": []},
        {"kind": "CALL"},
        {"acknowledgement_required": "true"},
        {"unexpected": "field"},
    ],
)
def test_invalid_creation_fails_without_writes(projects, change):
    service, sessions, owner, project, target = arrange(projects)
    with pytest.raises(ProjectError):
        service.create(lambda: owner, eligible, request(project, target, **change))
    with sessions() as s:
        assert s.scalar(select(CoordinationRecord)) is None


def test_future_response_contract_is_structured_and_rejects_identity_injection():
    assert (
        response_contract(
            "UPDATE", {"progress": "On track", "blockers": "None", "next_steps": "Review"}
        )["progress"]
        == "On track"
    )
    assert response_contract("MEETING", {"decision": "ACCEPT"}) == {"decision": "ACCEPT"}
    alternative = {
        "decision": "ALTERNATIVE",
        "alternative_time": "2030-01-10T10:00:00+05:30",
        "reason": "Prior commitment",
    }
    assert response_contract("CHECK_IN", alternative) == alternative
    for kind, value in [
        ("UPDATE", {"progress": "Done"}),
        ("MEETING", {"decision": "ACCEPT", "account_id": str(uuid4())}),
        ("MEETING", {**alternative, "alternative_time": "2030-01-10T10:00:00"}),
    ]:
        with pytest.raises(ProjectError):
            response_contract(kind, value)


def test_requester_revoked_during_recipient_lookup_cannot_commit(projects):
    service, sessions, owner, project, target = arrange(projects)
    current = [owner]

    def directory(account):
        current[0] = replace(owner, role="EMPLOYEE")
        return eligible(account)

    with pytest.raises(ProjectError):
        service.create(lambda: current[0], directory, request(project, target))
    with sessions() as session:
        assert session.scalar(select(CoordinationRecord)) is None


def test_owner_is_reloaded_after_waiting_for_transaction_lock(projects, monkeypatch):
    service, sessions, owner, project, target = arrange(projects)

    def transfer_while_waiting(session, issuer):
        with sessions() as other:
            other.get(Project, project["id"]).owner_id = str(uuid4())
            other.commit()

    monkeypatch.setattr("project_work.coordination.lock_company", transfer_while_waiting)
    with pytest.raises(ProjectError, match="project_not_found"):
        service.create(lambda: owner, eligible, request(project, target))
    with sessions() as session:
        assert session.scalar(select(CoordinationRecord)) is None
