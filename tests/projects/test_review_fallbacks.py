from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from project_work.memberships import MembershipService
from project_work.projects import ProjectError
from project_work.review_fallbacks import ReviewFallbackService

from .test_domain import create
from .test_domain import projects as projects
from .test_domain import setup as setup
from .test_memberships import appointment, eligible
from .test_owner_decisions import NOW, arrange


def record(project, **changes):
    return {
        "project_id": project["id"],
        "project_version": project["version"],
        "request_id": str(uuid4()),
        "leader_id": None,
        "scope": "REVIEWS",
        "reason": "Explicit leadership vacancy for this project",
        "starts_at": NOW.isoformat(),
        "ends_at": (NOW + timedelta(days=1)).isoformat(),
        "confirm": True,
        **changes,
    }


@pytest.mark.parametrize("roles", [{"ADMIN"}, {"ADMIN", "MANAGER"}])
def test_explicit_grant_policy_and_current_owner_receiver_are_separate(projects, roles):
    work, sessions, owner, *_ = projects
    project, _ = create(work, owner)
    service = ReviewFallbackService(sessions, roles, now=lambda: NOW)
    admin = replace(owner, role="ADMIN", account_id=str(uuid4()))
    with (
        sessions() as s,
        s.begin(),
        pytest.raises(ProjectError, match="explicit_fallback_required"),
    ):
        service.require_in_transaction(s, lambda: owner, project["id"], "REVIEWS")
    if "MANAGER" not in roles:
        with pytest.raises(ProjectError, match="fallback_recording_denied"):
            service.create(lambda: owner, record(project))
    request = record(project)
    result = service.create(lambda: admin, request)
    assert service.create(lambda: admin, request) == result and result["active"]
    with sessions() as s, s.begin():
        proof = service.require_in_transaction(s, lambda: owner, project["id"], "REVIEWS")
        assert proof["record_id"] == result["id"] and proof["actor_id"] == owner.account_id
        with pytest.raises(ProjectError, match="explicit_fallback_required"):
            service.require_in_transaction(s, lambda: owner, project["id"], "EXTENSIONS")


def test_disabled_recording_policy_never_defaults_to_privileged_access(projects):
    work, sessions, owner, *_ = projects
    project, _ = create(work, owner)
    service = ReviewFallbackService(sessions, frozenset(), now=lambda: NOW)
    with pytest.raises(ProjectError, match="fallback_recording_denied"):
        service.create(lambda: replace(owner, role="ADMIN"), record(project))
    assert not service.workspace(lambda: owner, project["id"])["can_record"]


def test_new_leader_invalidates_explicit_vacancy_without_granting_employee_authority(projects):
    work, sessions, owner, *_ = projects
    project, _ = create(work, owner)
    service = ReviewFallbackService(sessions, {"ADMIN", "MANAGER"}, now=lambda: NOW)
    service.create(lambda: owner, record(project))
    employee = replace(owner, role="EMPLOYEE", account_id=str(uuid4()))
    MembershipService(sessions).change(
        lambda: owner, eligible, appointment(project, employee.account_id, responsibility="LEADER")
    )
    assert not service.workspace(lambda: owner, project["id"])["records"][0]["active"]
    with sessions() as s, s.begin(), pytest.raises(ProjectError):
        service.require_in_transaction(s, lambda: employee, project["id"], "REVIEWS")


def test_absence_matches_exact_leader_and_revocation_retains_history(projects):
    work, sessions, owner, *_ = projects
    project, _ = create(work, owner)
    leader = str(uuid4())
    appointed = MembershipService(sessions).change(
        lambda: owner, eligible, appointment(project, leader, responsibility="LEADER")
    )
    project["version"] = appointed["version"]
    service = ReviewFallbackService(sessions, {"ADMIN", "MANAGER"}, now=lambda: NOW)
    with pytest.raises(ProjectError, match="stale_fallback_leader"):
        service.create(lambda: owner, record(project, leader_id=str(uuid4())))
    created = service.create(lambda: owner, record(project, leader_id=leader))
    value = {
        "project_id": project["id"],
        "record_id": created["id"],
        "request_id": str(uuid4()),
        "reason": "Leader returned",
        "confirm": True,
    }
    revoked = service.revoke(lambda: owner, value)
    assert service.revoke(lambda: owner, value) == revoked
    assert not revoked["active"] and revoked["reason"] == created["reason"]
    assert revoked["revoked_by"] == owner.account_id
    assert len(service.workspace(lambda: owner, project["id"])["records"]) == 1


def test_boundaries_require_current_period_and_scoped_authority(projects):
    work, sessions, owner, *_ = projects
    project, _ = create(work, owner)
    service = ReviewFallbackService(sessions, {"ADMIN", "MANAGER"}, now=lambda: NOW)
    service.create(lambda: owner, record(project, starts_at=(NOW + timedelta(hours=1)).isoformat()))
    assert not service.workspace(lambda: owner, project["id"])["records"][0]["active"]
    service.now = lambda: NOW + timedelta(hours=2)
    assert service.workspace(lambda: owner, project["id"])["records"][0]["active"]
    service.now = lambda: NOW + timedelta(days=1)
    assert not service.workspace(lambda: owner, project["id"])["records"][0]["active"]
    stranger = replace(owner, account_id=str(uuid4()))
    with pytest.raises(ProjectError):
        service.workspace(lambda: stranger, project["id"])


@pytest.mark.parametrize(
    "forecast, expected",
    [("2026-11-24T10:00:00Z", None), ("2026-11-26T11:30:00Z", "owner_deadline_decision_required")],
)
def test_extension_fallback_still_requires_assessed_within_deadline_impact(
    projects, forecast, expected
):
    _, sessions, owner, project, escalation = arrange(projects, forecast=forecast)
    from project_work.models import OwnerEscalation

    service = ReviewFallbackService(sessions, {"ADMIN", "MANAGER"}, now=lambda: NOW)
    service.create(lambda: owner, record(project, scope="EXTENSIONS"))
    with sessions() as session, session.begin():
        assessment_id = session.get(OwnerEscalation, escalation).assessment_id
        with pytest.raises(ProjectError, match="owner_assessment_required"):
            service.require_in_transaction(session, lambda: owner, project["id"], "EXTENSIONS")
        if expected:
            with pytest.raises(ProjectError, match=expected):
                service.require_in_transaction(
                    session, lambda: owner, project["id"], "EXTENSIONS", assessment_id
                )
        else:
            service.require_in_transaction(
                session, lambda: owner, project["id"], "EXTENSIONS", assessment_id
            )
