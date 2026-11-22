import json
from dataclasses import replace
from uuid import uuid4

import pytest
from project_work.memberships import MembershipService
from project_work.models import Project, ProjectMember, ProjectMembershipChange
from project_work.projects import ProjectError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .test_domain import create
from .test_domain import projects as projects
from .test_domain import setup as setup


def appointment(project, account_id, **changes):
    return {
        "project_id": project["id"],
        "request_id": str(uuid4()),
        "version": project["version"],
        "account_id": account_id,
        "action": "appoint",
        "responsibility": "CONTRIBUTOR",
        "duties": "Private responsibilities",
        "confirm": True,
        **changes,
    }


def eligible(account_id):
    return {
        "account_id": account_id,
        "display_name": "Source employee",
        "active": True,
        "role": "EMPLOYEE",
    }


def test_same_account_leads_one_project_contributes_elsewhere_and_cannot_manage(projects):
    work, sessions, owner, *_ = projects
    first, _ = create(work, owner, "First")
    second, _ = create(work, owner, "Second")
    third, _ = create(work, owner, "Unrelated")
    members = MembershipService(sessions)
    employee = replace(owner, account_id=str(uuid4()), role="EMPLOYEE")
    members.change(
        lambda: owner, eligible, appointment(first, employee.account_id, responsibility="LEADER")
    )
    members.change(lambda: owner, eligible, appointment(second, employee.account_id))
    assert members.workspace(lambda: employee, first["id"])["responsibility"] == "LEADER"
    assert members.workspace(lambda: employee, second["id"])["responsibility"] == "CONTRIBUTOR"
    assert {p["id"] for p in work.workspace(lambda: employee)["projects"]} == {
        first["id"],
        second["id"],
    }
    assert work.workspace(lambda: employee)["calendar"] is None
    assert work.workspace(lambda: employee, search="Unrelated")["projects"] == []
    with pytest.raises(ProjectError) as error:
        work.detail(lambda: employee, third["id"])
    assert error.value.code == "project_not_found"
    for command in (
        lambda: members.change(lambda: employee, eligible, appointment(first, str(uuid4()))),
        lambda: members.candidates(lambda: employee, first["id"], lambda *_: {}),
    ):
        with pytest.raises(ProjectError) as error:
            command()
        assert error.value.status == 403
    with pytest.raises(ProjectError) as error:
        work.preview(lambda: employee, {})
    assert error.value.status == 403


def test_revocation_is_immediate_and_history_and_deadline_survive(projects):
    work, sessions, owner, *_ = projects
    project, _ = create(work, owner)
    members = MembershipService(sessions)
    employee = replace(owner, account_id=str(uuid4()), role="EMPLOYEE")
    command = appointment(project, employee.account_id, responsibility="LEADER")
    result = members.change(lambda: owner, eligible, command)
    removed = members.change(
        lambda: owner,
        eligible,
        {**command, "request_id": str(uuid4()), "version": result["version"], "action": "remove"},
    )
    with pytest.raises(ProjectError):
        members.workspace(lambda: employee, project["id"])
    with pytest.raises(ProjectError):
        work.workspace(lambda: employee)
    view = members.workspace(lambda: owner, project["id"])
    assert view["members"][0]["active"] is False and len(view["history"]) == 2
    assert any(json.loads(r["after"])["active"] is False for r in view["history"])
    assert view["project"]["approved_deadline"] == project["approved_deadline"]
    assert view["project"]["creator_id"] == project["creator_id"]
    assert (
        members.change(
            lambda: owner,
            eligible,
            {**command, "request_id": str(uuid4()), "version": removed["version"]},
        )["version"]
        == 4
    )
    assert len(members.workspace(lambda: owner, project["id"])["members"]) == 1


@pytest.mark.parametrize("role", ["HR", "MANAGER", "ADMIN"])
def test_only_employee_targets_are_eligible(projects, role):
    work, sessions, owner, *_ = projects
    project, _ = create(work, owner)
    with pytest.raises(ProjectError) as error:
        MembershipService(sessions).change(
            lambda: owner,
            lambda account: {**eligible(account), "role": role},
            appointment(project, str(uuid4())),
        )
    assert error.value.code == "member_not_eligible"
    with sessions() as s:
        assert not s.scalar(select(ProjectMember.id)) and not s.scalar(
            select(ProjectMembershipChange.id)
        )


@pytest.mark.parametrize("target", ["inactive", "wrong_id", "missing_name"])
def test_ineligible_and_mismatched_target_cannot_receive_appointment(projects, target):
    work, sessions, owner, *_ = projects
    project, _ = create(work, owner)

    def candidate(account):
        value = eligible(account)
        value[
            {"inactive": "active", "wrong_id": "account_id", "missing_name": "display_name"}[target]
        ] = {"inactive": False, "wrong_id": str(uuid4()), "missing_name": None}[target]
        return value

    with pytest.raises(ProjectError) as error:
        MembershipService(sessions).change(
            lambda: owner, candidate, appointment(project, str(uuid4()))
        )
    assert error.value.code == "member_not_eligible"


def test_peers_cannot_read_another_members_duties_or_change_history(projects):
    work, sessions, owner, *_ = projects
    project, _ = create(work, owner)
    service = MembershipService(sessions)
    first, second = str(uuid4()), str(uuid4())
    r = service.change(
        lambda: owner, eligible, appointment(project, first, responsibility="LEADER")
    )
    service.change(
        lambda: owner,
        eligible,
        appointment(project, second, version=r["version"], duties="Peer private notes"),
    )
    view = service.workspace(
        lambda: replace(owner, account_id=first, role="EMPLOYEE"), project["id"]
    )
    assert view["history"] == [] and not view["can_manage"]
    own = next(r for r in view["members"] if r["account_id"] == first)
    peer = next(r for r in view["members"] if r["account_id"] is None)
    assert own["duties"] == "Private responsibilities" and peer["duties"] is None


def test_owner_and_admin_only_cross_company_and_unrelated_denial(projects):
    work, sessions, owner, *_ = projects
    project, _ = create(work, owner)
    service = MembershipService(sessions)
    for actor in (
        replace(owner, account_id=str(uuid4())),
        replace(owner, issuer="https://other.invalid", role="ADMIN"),
    ):
        with pytest.raises(ProjectError) as error:
            service.change(lambda: actor, eligible, appointment(project, str(uuid4())))
        assert error.value.code == "project_not_found"
    admin = replace(owner, account_id=str(uuid4()), role="ADMIN")
    assert (
        service.change(lambda: admin, eligible, appointment(project, str(uuid4())))["version"] == 2
    )


def test_leader_uniqueness_stale_edits_replay_and_conflicting_request(projects):
    work, sessions, owner, *_ = projects
    project, _ = create(work, owner)
    service = MembershipService(sessions)
    command = appointment(project, str(uuid4()), responsibility="LEADER")
    result = service.change(lambda: owner, eligible, command)
    assert (
        service.change(lambda: owner, lambda _: pytest.fail("Replay queried candidate"), command)
        == result
    )
    for change, code in (
        ({**command, "duties": "Changed"}, "request_conflict"),
        (appointment(project, str(uuid4())), "stale_project_membership"),
        (
            appointment(project, str(uuid4()), version=2, responsibility="LEADER"),
            "leader_already_appointed",
        ),
    ):
        with pytest.raises(ProjectError) as error:
            service.change(lambda: owner, eligible, change)
        assert error.value.code == code
    with sessions() as s, pytest.raises(IntegrityError):
        s.add(
            ProjectMember(
                issuer=owner.issuer,
                project_id=project["id"],
                account_id=str(uuid4()),
                display_name="Second",
                responsibility="LEADER",
                duties="",
                active=True,
            )
        )
        s.commit()


@pytest.mark.parametrize(
    "field,value",
    [("confirm", False), ("responsibility", "ADMIN"), ("version", True), ("duties", "x" * 1001)],
)
def test_invalid_changes_do_not_write(projects, field, value):
    work, sessions, owner, *_ = projects
    project, _ = create(work, owner)
    with pytest.raises(ProjectError):
        MembershipService(sessions).change(
            lambda: owner, eligible, appointment(project, str(uuid4()), **{field: value})
        )
    with sessions() as s:
        assert s.get(Project, project["id"]).version == 1
        assert s.scalar(select(ProjectMembershipChange.id)) is None


def test_authority_change_after_wait_does_not_write(projects):
    work, sessions, owner, *_ = projects
    project, _ = create(work, owner)
    calls = []

    def actor():
        calls.append(1)
        return owner if len(calls) == 1 else replace(owner, role="EMPLOYEE")

    with pytest.raises(ProjectError) as error:
        MembershipService(sessions).change(actor, eligible, appointment(project, str(uuid4())))
    assert error.value.code == "authority_changed"
