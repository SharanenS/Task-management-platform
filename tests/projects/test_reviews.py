import json
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from project_work.models import (
    ProjectMember,
    TaskExecution,
    TaskReviewDecision,
    TaskSchedule,
    TaskSubmission,
    WorkTask,
)
from project_work.projects import ProjectError
from project_work.review_fallbacks import ReviewFallbackService
from project_work.reviews import ReviewService
from project_work.scheduling import SchedulingService
from sqlalchemy import select

from .test_domain import projects as projects
from .test_domain import setup as setup
from .test_tasks import change, directory, prepare


def prepared(projects, own=False):
    tasks, sessions, owner, leader, employee, peer, project = prepare(projects)
    target = leader if own else employee
    receipt = tasks.change(lambda: leader, directory, change(project, target))
    project["version"] = receipt["project_version"]
    scheduling = SchedulingService(sessions)
    preview = scheduling.preview(
        lambda: leader,
        directory,
        {
            "project_id": project["id"],
            "task_id": receipt["task_id"],
            "version": receipt["version"],
            "project_version": project["version"],
            "requested_start": "2026-01-05",
            "duration": 3,
            "prerequisites": [],
            "reason": "Owned review schedule",
        },
    )
    saved = scheduling.commit(
        lambda: leader,
        directory,
        {
            "project_id": project["id"],
            "preview_id": preview["preview_id"],
            "request_id": str(uuid4()),
            "confirm": True,
        },
    )
    project["version"] = saved["project_version"]
    with sessions() as session:
        version = session.get(WorkTask, receipt["task_id"]).version
    receipt["version"] = version
    return (
        ReviewService(sessions, lambda: datetime(2026, 1, 6, 12, tzinfo=UTC)),
        sessions,
        owner,
        leader,
        target,
        peer,
        project,
        receipt,
    )


def execute(project, task, action="START", **fields):
    return {
        "project_id": project["id"],
        "task_id": task["task_id"],
        "project_version": project["version"],
        "version": task["version"],
        "request_id": str(uuid4()),
        "action": action,
        "note": "Owned completion evidence",
        "progress": 0,
        "blocker": None,
        "confirm": True,
        **fields,
    }


def act(service, target, project, task, action="START", **fields):
    value = execute(project, task, action, **fields)
    result = service.execute(lambda: target, directory, value)
    project["version"], task["version"] = result["project_version"], result["version"]
    return value, result


def decision(service, actor, project, task, outcome="APPROVE", **fields):
    row = service.workspace(lambda: actor, directory, project["id"])["tasks"][0]
    return {
        "project_id": project["id"],
        "task_id": task["task_id"],
        "submission_id": row["submissions"][0]["id"],
        "project_version": project["version"],
        "version": task["version"],
        "request_id": str(uuid4()),
        "outcome": outcome,
        "feedback": "Reviewed against criteria",
        "self_confirm": False,
        "confirm": True,
        **fields,
    }


def test_submission_is_separate_return_and_resubmit_retains_feedback_and_versions(projects):
    service, sessions, owner, leader, target, peer, project, task = prepared(projects)
    with sessions() as session:
        original = session.get(TaskSchedule, task["task_id"]).original
    start, receipt = act(service, target, project, task)
    assert service.execute(lambda: target, directory, start) == receipt
    act(service, target, project, task, "PROGRESS", progress=100, blocker="Recorded interruption")
    with sessions() as session:
        assert session.get(WorkTask, task["task_id"]).status == "IN_PROGRESS"
        assert session.get(TaskSchedule, task["task_id"]).original == original
    submitted, receipt = act(
        service, target, project, task, "SUBMIT", progress=100, blocker="Recorded interruption"
    )
    assert service.execute(lambda: target, directory, submitted) == receipt
    returned = decision(service, leader, project, task, "RETURN")
    result = service.decide(lambda: leader, directory, returned)
    assert service.decide(lambda: leader, directory, returned) == result
    project["version"], task["version"] = result["project_version"], result["version"]
    act(service, target, project, task, "PROGRESS", progress=80)
    act(service, target, project, task, "SUBMIT", progress=80)
    with pytest.raises(ProjectError, match="stale_review"):
        service.decide(lambda: leader, directory, {**returned, "request_id": str(uuid4())})
    final = decision(service, leader, project, task)
    result = service.decide(lambda: leader, directory, final)
    assert service.decide(lambda: leader, directory, final) == result
    with sessions() as session:
        assert session.get(WorkTask, task["task_id"]).status == "COMPLETED"
        assert session.get(TaskExecution, task["task_id"]).completed_at is not None
        assert session.get(TaskExecution, task["task_id"]).progress == 80
        assert session.get(TaskSchedule, task["task_id"]).original == original
        assert len(session.scalars(select(TaskSubmission)).all()) == 2
        assert [
            d.outcome
            for d in session.scalars(
                select(TaskReviewDecision).order_by(TaskReviewDecision.task_version)
            )
        ] == ["RETURN", "APPROVE"]


def test_leader_own_submission_requires_explicit_audited_self_approval(projects):
    service, sessions, owner, leader, target, peer, project, task = prepared(projects, own=True)
    act(service, target, project, task)
    act(service, target, project, task, "SUBMIT")
    value = decision(service, leader, project, task)
    with pytest.raises(ProjectError, match="explicit_self_approval_required"):
        service.decide(lambda: leader, directory, value)
    service.decide(lambda: leader, directory, {**value, "self_confirm": True})
    with sessions() as session:
        row = session.scalar(select(TaskReviewDecision))
        assert row.self_approval and row.actor_id == leader.account_id and row.fallback_id is None


@pytest.mark.parametrize("scope", ["REVIEWS", "BOTH", "EXTENSIONS"])
def test_owner_fallback_requires_live_review_scope_and_preserves_exact_record(projects, scope):
    service, sessions, owner, leader, target, peer, project, task = prepared(projects)
    act(service, target, project, task)
    act(service, target, project, task, "SUBMIT")
    value = decision(service, owner, project, task)
    with pytest.raises(ProjectError, match="explicit_fallback_required"):
        service.decide(lambda: owner, directory, value)
    fallback = ReviewFallbackService(sessions, {"ADMIN", "MANAGER"}, service.now)
    record = fallback.create(
        lambda: owner,
        {
            "project_id": project["id"],
            "request_id": str(uuid4()),
            "project_version": project["version"],
            "leader_id": leader.account_id,
            "scope": scope,
            "reason": "Approved absence",
            "starts_at": "2026-01-06T00:00:00Z",
            "ends_at": "2026-01-07T00:00:00Z",
            "confirm": True,
        },
    )
    if scope == "EXTENSIONS":
        with pytest.raises(ProjectError, match="explicit_fallback_required"):
            service.decide(lambda: owner, directory, value)
    else:
        service.decide(lambda: owner, directory, value)
        with sessions() as session:
            row = session.scalar(select(TaskReviewDecision))
            assert row.fallback_id == record["id"] and not row.self_approval


def test_peers_and_unrelated_managers_cannot_obtain_or_change_private_review_data(projects):
    service, sessions, owner, leader, target, peer, project, task = prepared(projects)
    value = execute(project, task)
    for actor in (owner, leader, peer):
        with pytest.raises(ProjectError):
            service.execute(lambda: actor, directory, value)
    act(service, target, project, task)
    act(service, target, project, task, "SUBMIT")
    assert service.workspace(lambda: peer, directory, project["id"])["tasks"] == []
    with pytest.raises(ProjectError):
        service.workspace(lambda: replace(owner, account_id=str(uuid4())), directory, project["id"])
    value = decision(service, target, project, task)
    with pytest.raises(ProjectError):
        service.decide(lambda: target, directory, value)


def test_revoked_leader_inactive_assignee_and_changed_authority_reject_decisions(projects):
    service, sessions, owner, leader, target, peer, project, task = prepared(projects)
    act(service, target, project, task)
    act(service, target, project, task, "SUBMIT")
    value = decision(service, leader, project, task)

    def inactive(ids):
        return [{**r, "active": False} for r in directory(ids)]

    with pytest.raises(ProjectError, match="task_assignee_ineligible"):
        service.decide(lambda: leader, inactive, value)
    with sessions() as session, session.begin():
        row = session.scalar(
            select(ProjectMember).where(ProjectMember.account_id == leader.account_id)
        )
        row.active = False
    with pytest.raises(ProjectError):
        service.decide(lambda: leader, directory, value)


@pytest.mark.parametrize("action", ["START", "PROGRESS", "SUBMIT"])
def test_execution_rejects_unconfirmed_and_stale_input(projects, action):
    service, _, _, _, target, _, project, task = prepared(projects)
    with pytest.raises(ProjectError):
        service.execute(lambda: target, directory, execute(project, task, action, confirm=False))
    with pytest.raises(ProjectError, match="stale_task"):
        service.execute(lambda: target, directory, execute(project, task, action, version=999))


def test_late_completion_keeps_commitments_and_does_not_claim_a_certain_forecast(projects):
    service, sessions, owner, leader, target, peer, project, task = prepared(projects)
    service.now = lambda: datetime(2026, 2, 1, tzinfo=UTC)
    service.scheduling.now = service.now
    act(service, target, project, task)
    act(service, target, project, task, "SUBMIT")
    service.decide(lambda: leader, directory, decision(service, leader, project, task))
    schedule = SchedulingService(sessions, service.now).workspace(
        lambda: owner, directory, project["id"]
    )
    assert (
        schedule["forecast_at"] is None
        and schedule["tasks"][0]["issue"] == "LATE_COMPLETION_REASSESSMENT"
    )
    with sessions() as session:
        assert json.loads(session.get(TaskSchedule, task["task_id"]).original)[
            "due_at"
        ] != utc_completion(session, task)


def utc_completion(session, task):
    return session.get(TaskExecution, task["task_id"]).completed_at.isoformat()


@pytest.mark.parametrize("boundary", ["expired", "revoked", "changed_leader"])
def test_fallback_is_rechecked_at_decision_time(projects, boundary):
    service, sessions, owner, leader, target, peer, project, task = prepared(projects)
    act(service, target, project, task)
    act(service, target, project, task, "SUBMIT")
    value = decision(service, owner, project, task)
    fallback = ReviewFallbackService(sessions, {"ADMIN", "MANAGER"}, service.now)
    record = fallback.create(
        lambda: owner,
        {
            "project_id": project["id"],
            "project_version": project["version"],
            "request_id": str(uuid4()),
            "leader_id": leader.account_id,
            "scope": "REVIEWS",
            "reason": "Explicit absence",
            "starts_at": "2026-01-06T00:00:00Z",
            "ends_at": "2026-01-07T00:00:00Z",
            "confirm": True,
        },
    )
    if boundary == "expired":
        service.now = lambda: datetime(2026, 1, 8, tzinfo=UTC)
        service.fallbacks.now = service.now
    elif boundary == "revoked":
        fallback.revoke(
            lambda: owner,
            {
                "project_id": project["id"],
                "record_id": record["id"],
                "request_id": str(uuid4()),
                "reason": "Leader returned",
                "confirm": True,
            },
        )
    else:
        with sessions() as session, session.begin():
            session.scalar(
                select(ProjectMember).where(ProjectMember.account_id == leader.account_id)
            ).active = False
    with pytest.raises(ProjectError, match="explicit_fallback_required"):
        service.decide(lambda: owner, directory, value)


def test_start_requires_completed_prerequisites_and_cannot_change_planned_dates(projects):
    from project_work.models import TaskDependency

    service, sessions, owner, leader, target, peer, project, task = prepared(projects)
    tasks = service.tasks
    other = tasks.change(lambda: leader, directory, change(project, peer))
    project["version"] = other["project_version"]
    with sessions() as session, session.begin():
        session.add(TaskDependency(task_id=task["task_id"], prerequisite_id=other["task_id"]))
    with pytest.raises(ProjectError, match="task_prerequisites_not_ready"):
        service.execute(lambda: target, directory, execute(project, task))


def test_request_conflict_and_current_authority_fencing_are_fail_closed(projects):
    service, sessions, owner, leader, target, peer, project, task = prepared(projects)
    value, result = act(service, target, project, task)
    with pytest.raises(ProjectError, match="task_request_conflict"):
        service.execute(lambda: target, directory, {**value, "note": "Different payload"})
    calls = iter([target, replace(target, display_name="Changed actor")])
    with pytest.raises(ProjectError, match="task_access_denied"):
        service.execute(lambda: next(calls), directory, execute(project, task, "PROGRESS"))


@pytest.mark.parametrize(
    "field,invalid",
    [("progress", True), ("progress", 101), ("progress", -1), ("note", ""), ("blocker", 42)],
)
def test_execution_validation_never_writes_invalid_values(projects, field, invalid):
    service, _, _, _, target, _, project, task = prepared(projects)
    with pytest.raises(ProjectError):
        service.execute(lambda: target, directory, execute(project, task, **{field: invalid}))


def test_completed_prerequisite_survives_former_assignee_deactivation(projects):
    service, sessions, owner, leader, target, peer, project, task = prepared(projects)
    act(service, target, project, task)
    act(service, target, project, task, "SUBMIT")
    result = service.decide(lambda: leader, directory, decision(service, leader, project, task))
    project["version"] = result["project_version"]
    child = service.tasks.change(lambda: leader, directory, change(project, leader))
    project["version"] = child["project_version"]
    scheduling = SchedulingService(sessions)
    preview = scheduling.preview(
        lambda: leader,
        directory,
        {
            "project_id": project["id"],
            "task_id": child["task_id"],
            "version": child["version"],
            "project_version": project["version"],
            "requested_start": "2026-01-08",
            "duration": 1,
            "prerequisites": [task["task_id"]],
            "reason": "Dependent work after approved completion",
        },
    )
    saved = scheduling.commit(
        lambda: leader,
        directory,
        {
            "project_id": project["id"],
            "preview_id": preview["preview_id"],
            "request_id": str(uuid4()),
            "confirm": True,
        },
    )
    project["version"] = saved["project_version"]
    with sessions() as session:
        child["version"] = session.get(WorkTask, child["task_id"]).version

    def active_child_only(ids):
        return [{**r, "active": r["account_id"] != target.account_id} for r in directory(ids)]

    service.now = lambda: datetime(2026, 1, 9, 12, tzinfo=UTC)
    service.scheduling.now = service.now
    service.execute(lambda: leader, active_child_only, execute(project, child))
    with sessions() as session:
        assert session.get(WorkTask, task["task_id"]).status == "COMPLETED"
        assert session.get(WorkTask, child["task_id"]).status == "IN_PROGRESS"
