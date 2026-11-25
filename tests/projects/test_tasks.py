import json
from dataclasses import replace
from uuid import uuid4

import pytest
from project_work.memberships import MembershipService
from project_work.models import DeliveryState, ProjectMember, TaskAssignment, TaskChange, WorkTask
from project_work.projects import ProjectError
from project_work.tasks import TaskService
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .test_domain import create
from .test_domain import projects as projects
from .test_domain import setup as setup
from .test_memberships import appointment, eligible


def prepare(projects):
    work, sessions, owner, *_ = projects
    project, _ = create(work, owner)
    leader = replace(owner, account_id=str(uuid4()), role="EMPLOYEE", display_name="Leader")
    employee = replace(leader, account_id=str(uuid4()), display_name="Employee")
    peer = replace(employee, account_id=str(uuid4()), display_name="Peer")
    members = MembershipService(sessions)
    for actor, responsibility in (
        (leader, "LEADER"),
        (employee, "CONTRIBUTOR"),
        (peer, "CONTRIBUTOR"),
    ):
        project["version"] = members.change(
            lambda: owner,
            eligible,
            appointment(project, actor.account_id, responsibility=responsibility),
        )["version"]
    return TaskService(sessions), sessions, owner, leader, employee, peer, project


def directory(ids):
    return [eligible(i) for i in ids]


def change(project, target, **fields):
    return {
        "project_id": project["id"],
        "project_version": project["version"],
        "request_id": str(uuid4()),
        "task_id": None,
        "version": 0,
        "action": "CREATE",
        "title": "Owned task",
        "instructions": "Private instructions",
        "acceptance_criteria": "Private acceptance",
        "assignee_id": target.account_id,
        "reason": "Planning reason",
        "confirm": True,
        **fields,
    }


def test_create_edit_reassign_retains_history_and_single_owner(projects):
    tasks, sessions, owner, leader, employee, peer, project = prepare(projects)
    value = change(project, employee)
    first = tasks.change(lambda: leader, directory, value)
    assert tasks.change(lambda: leader, directory, value) == first
    edited = tasks.change(
        lambda: leader,
        directory,
        change(
            project,
            employee,
            action="EDIT",
            task_id=first["task_id"],
            version=first["version"],
            project_version=first["project_version"],
            assignee_id=None,
            instructions="Revised private instruction",
        ),
    )
    assigned = tasks.change(
        lambda: leader,
        directory,
        change(
            project,
            leader,
            action="ASSIGN",
            task_id=first["task_id"],
            version=edited["version"],
            project_version=edited["project_version"],
            title=None,
            instructions=None,
            acceptance_criteria=None,
        ),
    )
    assert assigned["version"] == 3
    with sessions() as s:
        rows = s.scalars(select(TaskAssignment)).all()
        assert len(rows) == 2 and sum(r.ended_at is None for r in rows) == 1
        assert next(r for r in rows if r.account_id == employee.account_id).ended_at
        history = s.scalars(select(TaskChange).order_by(TaskChange.task_version)).all()
        assert len(history) == 3
        assert json.loads(history[2].before)["assignee_id"] == employee.account_id
        assert json.loads(history[2].after)["assignee_id"] == leader.account_id
        assert json.loads(history[2].after)["assignee_name"] == "Source employee"
        assert s.get(DeliveryState, project["id"]).schedule_version == 3
    assert tasks.workspace(lambda: employee, project["id"])["tasks"][0]["details"] is None
    assert tasks.workspace(lambda: leader, project["id"])["tasks"][0]["details"]["version"] == 3


@pytest.mark.parametrize("actor_index", [2, 4, 5])
def test_only_contextual_leader_plans_even_owner_and_admin_do_not_impersonate(
    projects, actor_index
):
    fixture = prepare(projects)
    tasks, _, owner, leader, employee, peer, project = fixture
    actor = fixture[actor_index]
    for candidate in (actor, replace(actor, role="ADMIN")):
        with pytest.raises(ProjectError) as error:
            tasks.change(lambda: candidate, directory, change(project, employee))
        assert error.value.status == 403


def test_member_peer_and_current_assignee_private_fields(projects):
    tasks, _, owner, leader, employee, peer, project = prepare(projects)
    tasks.change(lambda: leader, directory, change(project, employee))
    for actor in (leader, owner, replace(owner, role="ADMIN"), employee):
        row = tasks.workspace(lambda: actor, project["id"])["tasks"][0]
        assert row["details"]["instructions"] == "Private instructions"
        if actor == employee:
            assert row["details"]["history"] == []
    row = tasks.workspace(lambda: peer, project["id"])["tasks"][0]
    assert set(row) == {"id", "title", "status", "assignee_name", "details"}
    assert row["details"] is None


@pytest.mark.parametrize("role", ["EMPLOYEE", "MANAGER", "HR", "ADMIN"])
def test_unrelated_and_cross_issuer_scope(projects, role):
    tasks, _, owner, leader, employee, _, project = prepare(projects)
    outsider = replace(owner, account_id=str(uuid4()), role=role)
    if role != "ADMIN":
        with pytest.raises(ProjectError):
            tasks.workspace(lambda: outsider, project["id"])
    with pytest.raises(ProjectError):
        tasks.workspace(lambda: replace(outsider, issuer="https://other.invalid"), project["id"])
    with pytest.raises(ProjectError):
        tasks.change(lambda: outsider, directory, change(project, employee))


@pytest.mark.parametrize("case", ["missing", "inactive", "manager", "hr", "wrong-id"])
def test_live_assignee_eligibility_fails_closed(projects, case):
    tasks, sessions, _, leader, employee, _, project = prepare(projects)
    row = eligible(employee.account_id)
    if case == "inactive":
        row["active"] = False
    if case in {"manager", "hr"}:
        row["role"] = case.upper()
    if case == "wrong-id":
        row["account_id"] = str(uuid4())
    with pytest.raises(ProjectError, match="task_assignee_ineligible"):
        tasks.change(
            lambda: leader,
            lambda ids: [] if case == "missing" else [row],
            change(project, employee),
        )
    with sessions() as s:
        assert not s.scalar(select(WorkTask.id))
        assert not s.scalar(select(DeliveryState.project_id))


def test_nonmember_target_never_reaches_people_lookup(projects):
    tasks, _, _, leader, employee, _, project = prepare(projects)

    def forbidden(ids):
        raise AssertionError("Unscoped directory call")

    with pytest.raises(ProjectError, match="task_assignee_ineligible"):
        tasks.change(
            lambda: leader, forbidden, change(project, replace(employee, account_id=str(uuid4())))
        )


def test_stale_and_conflicting_requests_leave_one_task(projects):
    tasks, sessions, _, leader, employee, _, project = prepare(projects)
    value = change(project, employee)
    result = tasks.change(lambda: leader, directory, value)
    with pytest.raises(ProjectError, match="task_request_conflict"):
        tasks.change(lambda: leader, directory, {**value, "title": "Changed"})
    with pytest.raises(ProjectError, match="stale_task"):
        tasks.change(lambda: leader, directory, change(project, employee))
    with pytest.raises(ProjectError, match="stale_task"):
        tasks.change(
            lambda: leader,
            directory,
            {
                **value,
                "request_id": str(uuid4()),
                "action": "EDIT",
                "task_id": result["task_id"],
                "version": 0,
                "project_version": result["project_version"],
                "assignee_id": None,
            },
        )
    with sessions() as s:
        assert len(s.scalars(select(WorkTask)).all()) == 1


def test_leader_revocation_and_project_context_rechecked(projects):
    tasks, sessions, owner, leader, employee, _, project = prepare(projects)
    work = projects[0]
    other, _ = create(work, owner, "Other")
    with pytest.raises(ProjectError):
        tasks.change(lambda: leader, directory, change(other, employee))
    with sessions() as s, s.begin():
        r = s.scalar(select(ProjectMember).where(ProjectMember.account_id == leader.account_id))
        r.responsibility = "CONTRIBUTOR"
    with pytest.raises(ProjectError, match="task_planning_denied"):
        tasks.change(lambda: leader, directory, change(project, employee))


@pytest.mark.parametrize(
    "field,value",
    [
        ("confirm", False),
        ("version", True),
        ("title", ""),
        ("instructions", " "),
        ("acceptance_criteria", ""),
        ("action", "COMPLETE"),
    ],
)
def test_invalid_commands_never_write(projects, field, value):
    tasks, sessions, _, leader, employee, _, project = prepare(projects)
    with pytest.raises(ProjectError):
        tasks.change(lambda: leader, directory, {**change(project, employee), field: value})
    with sessions() as s:
        assert not s.scalar(select(WorkTask.id))


def test_database_prevents_duplicate_active_assignment(projects):
    tasks, sessions, _, leader, employee, _, project = prepare(projects)
    result = tasks.change(lambda: leader, directory, change(project, employee))
    with pytest.raises(IntegrityError), sessions() as s, s.begin():
        s.add(
            TaskAssignment(
                task_id=result["task_id"],
                account_id=leader.account_id,
                display_name="Leader",
                actor_id=leader.account_id,
            )
        )
        s.flush()


def test_candidates_current_scope_and_paging(projects):
    tasks, _, owner, leader, employee, peer, project = prepare(projects)
    values = tasks.candidates(lambda: leader, project["id"], directory)
    assert {v["account_id"] for v in values["candidates"]} == {
        leader.account_id,
        employee.account_id,
        peer.account_id,
    }
    assert tasks.candidates(lambda: leader, project["id"], lambda ids: [])["candidates"] == []
    for actor in (owner, employee):
        with pytest.raises(ProjectError):
            tasks.candidates(lambda: actor, project["id"], directory)
    with pytest.raises(ProjectError):
        tasks.workspace(lambda: leader, project["id"], -1)
