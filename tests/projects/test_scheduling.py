import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from project_work.models import (
    DeliveryAssessment,
    DeliveryState,
    Project,
    ScheduleChange,
    SchedulePreview,
    TaskSchedule,
    WorkTask,
)
from project_work.projects import ProjectError, utc
from project_work.scheduling import SchedulingService
from sqlalchemy import select

from .test_domain import projects as projects
from .test_domain import setup as setup
from .test_tasks import change, directory, prepare


def prepared(projects):
    tasks, sessions, owner, leader, employee, peer, project = prepare(projects)
    receipts = []
    for assignee in (employee, leader):
        receipt = tasks.change(lambda: leader, directory, change(project, assignee))
        project["version"] = receipt["project_version"]
        receipts.append(receipt)
    service = SchedulingService(sessions, lambda: datetime(2026, 1, 1, tzinfo=UTC))
    return service, sessions, owner, leader, employee, peer, project, receipts


def plan(project, receipt, **fields):
    return {
        "project_id": project["id"],
        "task_id": receipt["task_id"],
        "project_version": project["version"],
        "version": receipt["version"],
        "requested_start": "2026-01-02",
        "duration": 2,
        "prerequisites": [],
        "reason": "Reviewed plan",
        **fields,
    }


def commit(project, preview):
    return {
        "project_id": project["id"],
        "preview_id": preview["preview_id"],
        "request_id": str(uuid4()),
        "confirm": True,
    }


def test_preview_confirmation_pins_original_and_keeps_parallel_forecast_honest(projects):
    service, sessions, owner, leader, employee, peer, project, receipts = prepared(projects)
    original_deadline = project["approved_deadline"]
    preview = service.preview(lambda: leader, directory, plan(project, receipts[0]))
    assert preview["after"]["state"] == "UNASSESSED"
    value = commit(project, preview)
    saved = service.commit(lambda: leader, directory, value)
    assert service.commit(lambda: leader, directory, value) == saved
    project["version"] = saved["project_version"]
    preview = service.preview(
        lambda: leader,
        directory,
        plan(project, receipts[1], prerequisites=[receipts[0]["task_id"]]),
    )
    assert preview["after"]["state"] == "ASSESSED"
    assert preview["after"]["tasks"][1]["effective_start"] == "2026-01-06"
    saved = service.commit(lambda: leader, directory, commit(project, preview))
    workspace = service.workspace(lambda: owner, directory, project["id"])
    assert not workspace["can_plan"] and workspace["state"] == "ASSESSED"
    assert len(workspace["history"]) == 2
    assert workspace["project"]["approved_deadline"] == original_deadline
    with sessions() as session:
        first = session.get(TaskSchedule, receipts[0]["task_id"])
        original = first.original
        version = session.get(WorkTask, first.task_id).version
    project["version"] = saved["project_version"]
    preview = service.preview(
        lambda: leader, directory, plan(project, receipts[0], version=version, duration=4)
    )
    service.commit(lambda: leader, directory, commit(project, preview))
    with sessions() as session:
        first = session.get(TaskSchedule, receipts[0]["task_id"])
        assert first.original == original and first.current != original
        assert (
            session.get(Project, project["id"]).approved_deadline.isoformat() in original_deadline
        )


@pytest.mark.parametrize("actor_name", ["owner", "employee", "peer", "admin"])
def test_only_current_project_leader_can_preview(projects, actor_name):
    service, sessions, owner, leader, employee, peer, project, receipts = prepared(projects)
    actor = {
        "owner": owner,
        "employee": employee,
        "peer": peer,
        "admin": replace(owner, role="ADMIN"),
    }[actor_name]
    with pytest.raises(ProjectError) as error:
        service.preview(lambda: actor, directory, plan(project, receipts[0]))
    assert error.value.status == 403


def test_peer_projection_excludes_other_dates_history_forecast_and_overlap(projects):
    service, sessions, owner, leader, employee, peer, project, receipts = prepared(projects)
    preview = service.preview(lambda: leader, directory, plan(project, receipts[0]))
    service.commit(lambda: leader, directory, commit(project, preview))
    own = service.workspace(lambda: employee, directory, project["id"])
    assert [row["id"] for row in own["tasks"]] == [receipts[0]["task_id"]]
    assert own["history"] == own["overlaps"] == [] and own["forecast_at"] is None
    empty = service.workspace(lambda: peer, directory, project["id"])
    assert empty["tasks"] == [] and empty["state"] is None


@pytest.mark.parametrize("mutation", ["expired", "changed", "eligibility", "revoked"])
def test_preview_cannot_survive_stale_authority_or_inputs(projects, mutation):
    service, sessions, owner, leader, employee, peer, project, receipts = prepared(projects)
    preview = service.preview(lambda: leader, directory, plan(project, receipts[0]))
    actor = leader
    reference = directory
    if mutation == "expired":
        service.now = lambda: datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=11)
    if mutation == "changed":
        with sessions() as session, session.begin():
            session.get(WorkTask, receipts[1]["task_id"]).version += 1
    if mutation == "eligibility":

        def reference(ids):
            return []

    if mutation == "revoked":
        actor = replace(leader, role="HR")
    with pytest.raises(ProjectError):
        service.commit(lambda: actor, reference, commit(project, preview))
    with sessions() as session:
        assert not session.scalar(select(ScheduleChange))
        assert not session.scalar(select(TaskSchedule))


def test_preview_is_actor_bound_and_exact_replay_is_payload_bound(projects):
    service, sessions, owner, leader, employee, peer, project, receipts = prepared(projects)
    preview = service.preview(lambda: leader, directory, plan(project, receipts[0]))
    with sessions() as session, session.begin():
        session.get(SchedulePreview, preview["preview_id"]).actor_id = peer.account_id
    with pytest.raises(ProjectError):
        service.commit(lambda: leader, directory, commit(project, preview))
    with sessions() as session, session.begin():
        session.get(SchedulePreview, preview["preview_id"]).actor_id = leader.account_id
    value = commit(project, preview)
    service.commit(lambda: leader, directory, value)
    with pytest.raises(ProjectError):
        service.commit(lambda: leader, directory, {**value, "preview_id": str(uuid4())})


def test_unscheduled_old_tasks_remain_unknown_and_no_dates_are_seeded(projects):
    service, sessions, owner, leader, employee, peer, project, receipts = prepared(projects)
    view = service.workspace(lambda: leader, directory, project["id"])
    assert view["forecast_at"] is None and view["state"] == "UNASSESSED"
    assert all(row["requested_start"] is None for row in view["tasks"])
    with sessions() as session:
        assert not session.scalar(select(TaskSchedule))


def test_future_start_guard_requires_current_assignee_date_and_approved_prerequisites(projects):
    service, sessions, owner, leader, employee, peer, project, receipts = prepared(projects)
    preview = service.preview(lambda: leader, directory, plan(project, receipts[0]))
    saved = service.commit(lambda: leader, directory, commit(project, preview))
    project["version"] = saved["project_version"]
    preview = service.preview(
        lambda: leader,
        directory,
        plan(project, receipts[1], prerequisites=[receipts[0]["task_id"]]),
    )
    service.commit(lambda: leader, directory, commit(project, preview))
    with sessions() as session, session.begin():
        with pytest.raises(ProjectError) as error:
            service.require_ready_in_transaction(
                session, lambda: employee, project["id"], receipts[0]["task_id"], directory
            )
        assert error.value.code == "task_prerequisites_not_ready"
    service.now = lambda: datetime(2026, 1, 6, 6, tzinfo=UTC)
    with sessions() as session, session.begin():
        with pytest.raises(ProjectError) as error:
            service.require_ready_in_transaction(
                session, lambda: leader, project["id"], receipts[1]["task_id"], directory
            )
        assert error.value.code == "task_prerequisites_not_ready"
    with sessions() as session, session.begin():
        session.get(WorkTask, receipts[0]["task_id"]).status = "AWAITING_REVIEW"
    with sessions() as session, session.begin():
        with pytest.raises(ProjectError):
            service.require_ready_in_transaction(
                session, lambda: leader, project["id"], receipts[1]["task_id"], directory
            )
    with sessions() as session, session.begin():
        session.get(WorkTask, receipts[0]["task_id"]).status = "COMPLETED"
    with sessions() as session, session.begin():
        result = service.require_ready_in_transaction(
            session, lambda: leader, project["id"], receipts[1]["task_id"], directory
        )
        assert result["readiness"] == "READY"
    with sessions() as session, session.begin():
        with pytest.raises(ProjectError) as error:
            service.require_ready_in_transaction(
                session, lambda: owner, project["id"], receipts[1]["task_id"], directory
            )
        assert error.value.status == 403


def test_preview_rejects_a_schedule_generation_change_even_without_project_version_change(projects):
    service, sessions, owner, leader, employee, peer, project, receipts = prepared(projects)
    preview = service.preview(lambda: leader, directory, plan(project, receipts[0]))
    with sessions() as session, session.begin():
        session.get(DeliveryState, project["id"]).schedule_version += 1
    with pytest.raises(ProjectError) as error:
        service.commit(lambda: leader, directory, commit(project, preview))
    assert error.value.code == "stale_schedule"


def test_dependency_revision_rejects_changes_to_started_work(projects):
    service, sessions, owner, leader, employee, peer, project, receipts = prepared(projects)
    saved = service.commit(
        lambda: leader,
        directory,
        commit(project, service.preview(lambda: leader, directory, plan(project, receipts[0]))),
    )
    project["version"] = saved["project_version"]
    saved = service.commit(
        lambda: leader,
        directory,
        commit(
            project,
            service.preview(
                lambda: leader,
                directory,
                plan(project, receipts[1], prerequisites=[receipts[0]["task_id"]]),
            ),
        ),
    )
    project["version"] = saved["project_version"]
    with sessions() as session, session.begin():
        session.get(WorkTask, receipts[1]["task_id"]).status = "IN_PROGRESS"
        version = session.get(WorkTask, receipts[0]["task_id"]).version
    with pytest.raises(ProjectError) as error:
        service.preview(
            lambda: leader, directory, plan(project, receipts[0], version=version, duration=10)
        )
    assert error.value.code == "schedule_affects_started_task"


def test_late_start_readiness_keeps_original_dates_and_unknown_forecast(projects):
    service, sessions, owner, leader, employee, peer, project, receipts = prepared(projects)
    service.commit(
        lambda: leader,
        directory,
        commit(project, service.preview(lambda: leader, directory, plan(project, receipts[0]))),
    )
    with sessions() as session:
        original = session.get(TaskSchedule, receipts[0]["task_id"]).original
    service.now = lambda: datetime(2026, 2, 1, tzinfo=UTC)
    with sessions() as session, session.begin():
        result = service.require_ready_in_transaction(
            session, lambda: employee, project["id"], receipts[0]["task_id"], directory
        )
        assert result["readiness"] == "READY" and result["issue"] == "INCOMPLETE_PAST_FINISH"
        assert session.get(TaskSchedule, receipts[0]["task_id"]).original == original
        assert session.get(WorkTask, receipts[0]["task_id"]).status == "PENDING"
    assert service.workspace(lambda: owner, directory, project["id"])["forecast_at"] is None


def test_assessment_cannot_outlive_an_exact_finish_cutoff(projects):
    service, sessions, owner, leader, employee, peer, project, receipts = prepared(projects)
    for receipt in receipts:
        saved = service.commit(
            lambda: leader,
            directory,
            commit(project, service.preview(lambda: leader, directory, plan(project, receipt))),
        )
        project["version"] = saved["project_version"]
    with sessions() as session:
        first = session.get(TaskSchedule, receipts[0]["task_id"])
        due = datetime.fromisoformat(json.loads(first.current)["due_at"])
        version = session.get(WorkTask, receipts[0]["task_id"]).version
    service.now = lambda: due
    service.commit(
        lambda: leader,
        directory,
        commit(
            project,
            service.preview(lambda: leader, directory, plan(project, receipts[0], version=version)),
        ),
    )
    with sessions() as session:
        assessment = session.scalars(
            select(DeliveryAssessment)
            .where(DeliveryAssessment.project_id == project["id"])
            .order_by(DeliveryAssessment.schedule_version.desc())
        ).first()
        assert datetime.fromisoformat(utc(assessment.valid_until)) <= due
