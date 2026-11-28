"""Approved runtime only: synthetic-issuer schedule races and exact cleanup."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from project_work.memberships import MembershipService
from project_work.models import (
    Base,
    CalendarPreview,
    CalendarVersion,
    DeliveryAssessment,
    DeliveryState,
    Project,
    ProjectMember,
    ProjectMembershipChange,
    ProjectPreview,
    ScheduleChange,
    SchedulePreview,
    TaskAssignment,
    TaskChange,
    TaskDependency,
    TaskSchedule,
    WorkTask,
)
from project_work.projects import ProjectActor, ProjectError, ProjectService
from project_work.scheduling import SchedulingService
from project_work.service import CalendarService
from project_work.tasks import TaskService
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker


def main():
    engine = create_engine(os.environ["PROJECT_WORK_DATABASE_URL"], hide_parameters=True)
    if engine.url.host != "project-work-db" or engine.url.database != "taskspace_project_work":
        raise ValueError("Wrong database boundary")
    sessions = sessionmaker(engine)
    run = str(uuid4())
    issuer = "https://s12-probe.invalid/" + run
    owner = ProjectActor(issuer, str(uuid4()), "ADMIN", "Probe owner")
    leader = ProjectActor(issuer, str(uuid4()), "EMPLOYEE", "Probe leader")
    employee = ProjectActor(issuer, str(uuid4()), "EMPLOYEE", "Probe employee")
    actors = {owner.account_id, leader.account_id, employee.account_id}
    stage, failed = "schema parity", False

    def directory(values):
        return [
            {"account_id": v, "display_name": "Owned " + run, "role": "EMPLOYEE", "active": True}
            for v in values
            if v in actors - {owner.account_id}
        ]

    try:
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        stage = "owned calendar and project"
        calendar = CalendarService(sessions)
        config = {
            "timezone": "Asia/Colombo",
            "week": [
                {
                    "weekday": i,
                    "working": i < 6,
                    "opens": "09:00" if i < 6 else None,
                    "closes": "17:00" if i < 6 else None,
                }
                for i in range(1, 8)
            ],
            "holidays": [],
            "exceptions": [],
        }

        def authority():
            return issuer, owner.account_id

        preview = calendar.preview(authority, config)
        calendar.publish(
            authority,
            {"request_id": str(uuid4()), "preview_id": preview["preview_id"], "confirm": True},
        )
        work = ProjectService(sessions)
        preview = work.preview(
            lambda: owner,
            {
                "name": "Owned " + run,
                "objectives": "Schedule probe " + run,
                "deadline_date": "2030-12-31",
            },
        )
        project = work.create(
            lambda: owner,
            {"request_id": str(uuid4()), "preview_id": preview["preview_id"], "confirm": True},
        )
        original = project["approved_deadline"]
        members = MembershipService(sessions)
        for actor, responsibility in ((leader, "LEADER"), (employee, "CONTRIBUTOR")):
            project["version"] = members.change(
                lambda: owner,
                lambda account: directory([account])[0],
                {
                    "project_id": project["id"],
                    "version": project["version"],
                    "request_id": str(uuid4()),
                    "account_id": actor.account_id,
                    "action": "appoint",
                    "responsibility": responsibility,
                    "duties": "Owned " + run,
                    "confirm": True,
                },
            )["version"]
        task_service = TaskService(sessions)
        tasks = []
        for i in range(2):
            task = task_service.change(
                lambda: leader,
                directory,
                {
                    "project_id": project["id"],
                    "project_version": project["version"],
                    "request_id": str(uuid4()),
                    "action": "CREATE",
                    "task_id": None,
                    "version": 0,
                    "title": "Owned task " + str(i),
                    "instructions": "Owned " + run,
                    "acceptance_criteria": "Owned " + run,
                    "assignee_id": employee.account_id,
                    "reason": "Owned " + run,
                    "confirm": True,
                },
            )
            tasks.append(task)
            project["version"] = task["project_version"]
        service = SchedulingService(sessions, lambda: datetime(2029, 1, 1, tzinfo=UTC))

        def plan(index, duration, dependencies=None):
            current = task_service.workspace(lambda: leader, project["id"])
            target = next(t for t in current["tasks"] if t["id"] == tasks[index]["task_id"])
            return service.preview(
                lambda: leader,
                directory,
                {
                    "project_id": project["id"],
                    "project_version": current["project"]["version"],
                    "task_id": target["id"],
                    "version": target["details"]["version"],
                    "requested_start": "2030-01-04",
                    "duration": duration,
                    "prerequisites": dependencies or [],
                    "reason": "Owned " + run,
                },
            )

        def command(preview):
            return {
                "project_id": project["id"],
                "preview_id": preview["preview_id"],
                "request_id": str(uuid4()),
                "confirm": True,
            }

        stage = "competing confirmed schedules"
        commands = [command(plan(0, duration)) for duration in (2, 3)]
        barrier = Barrier(2)

        def compete(value):
            barrier.wait()
            try:
                return ("saved", service.commit(lambda: leader, directory, value), value)
            except ProjectError as error:
                return (error.code, None, value)

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(compete, commands))
        assert sorted(row[0] for row in outcomes) == ["saved", "stale_schedule"]
        winner = next(row for row in outcomes if row[0] == "saved")
        assert service.commit(lambda: leader, directory, winner[2]) == winner[1]
        stage = "dependency handoff and retained history"
        service.commit(lambda: leader, directory, command(plan(1, 2, [tasks[0]["task_id"]])))
        view = service.workspace(lambda: owner, directory, project["id"])
        assert view["state"] == "ASSESSED" and len(view["history"]) == 2
        assert view["project"]["approved_deadline"] == original
        assert view["tasks"][1]["starts_at"] > view["tasks"][0]["due_at"]
        stage = "cycle rejection"
        try:
            plan(0, 2, [tasks[1]["task_id"]])
            raise AssertionError("cycle accepted")
        except ProjectError as error:
            assert error.code == "dependency_cycle"
        print(
            json.dumps(
                {
                    "kind": "passed",
                    "race_winners": 1,
                    "cycle_rejected": True,
                    "original_deadline_preserved": True,
                }
            ),
            flush=True,
        )
    except Exception:
        failed = True
        print(json.dumps({"kind": "failure", "stage": stage}), flush=True)
    finally:
        try:
            with sessions() as session, session.begin():
                projects = session.scalars(select(Project).where(Project.issuer == issuer)).all()
                if any(
                    p.creator_id != owner.account_id or p.name != "Owned " + run for p in projects
                ):
                    raise ValueError("Foreign project")
                pids = [p.id for p in projects]
                tasks_owned = session.scalars(
                    select(WorkTask).where(WorkTask.project_id.in_(pids))
                ).all()
                if any(t.creator_id not in actors for t in tasks_owned):
                    raise ValueError("Foreign task")
                tids = [t.id for t in tasks_owned]
                for model in (TaskChange, TaskAssignment):
                    owned_rows = session.scalars(select(model).where(model.task_id.in_(tids))).all()
                    if any(r.actor_id != leader.account_id for r in owned_rows):
                        raise ValueError("Foreign task actor")
                    if model is TaskAssignment and any(
                        r.account_id not in actors for r in owned_rows
                    ):
                        raise ValueError("Foreign assignee")
                appointments = session.scalars(
                    select(ProjectMember).where(ProjectMember.project_id.in_(pids))
                ).all()
                if any(r.account_id not in actors for r in appointments):
                    raise ValueError("Foreign appointment")
                changes = session.scalars(
                    select(ProjectMembershipChange).where(
                        ProjectMembershipChange.project_id.in_(pids)
                    )
                ).all()
                if any(
                    r.actor_id != owner.account_id or r.target_id not in actors for r in changes
                ):
                    raise ValueError("Foreign membership history")
                previews = session.scalars(
                    select(ProjectPreview).where(ProjectPreview.issuer == issuer)
                ).all()
                if any(r.actor_id != owner.account_id for r in previews):
                    raise ValueError("Foreign project preview")
                for model in (ScheduleChange, SchedulePreview):
                    rows = session.scalars(select(model).where(model.project_id.in_(pids))).all()
                    if any(r.actor_id not in actors for r in rows):
                        raise ValueError("Foreign schedule actor")
                edges = session.scalars(
                    select(TaskDependency).where(
                        TaskDependency.task_id.in_(tids) | TaskDependency.prerequisite_id.in_(tids)
                    )
                ).all()
                if any(e.task_id not in tids or e.prerequisite_id not in tids for e in edges):
                    raise ValueError("Foreign dependency")
                for model in (ScheduleChange, SchedulePreview, DeliveryAssessment, DeliveryState):
                    session.execute(delete(model).where(model.project_id.in_(pids)))
                for model in (TaskDependency, TaskSchedule, TaskChange, TaskAssignment):
                    session.execute(delete(model).where(model.task_id.in_(tids)))
                session.execute(delete(WorkTask).where(WorkTask.id.in_(tids)))
                for model in (ProjectMembershipChange, ProjectMember):
                    session.execute(delete(model).where(model.project_id.in_(pids)))
                session.execute(delete(Project).where(Project.id.in_(pids)))
                session.execute(delete(ProjectPreview).where(ProjectPreview.issuer == issuer))
                versions = session.scalars(
                    select(CalendarVersion).where(CalendarVersion.issuer == issuer)
                ).all()
                if any(v.actor_id != owner.account_id for v in versions):
                    raise ValueError("Foreign calendar actor")
                session.execute(delete(CalendarVersion).where(CalendarVersion.issuer == issuer))
                session.execute(delete(CalendarPreview).where(CalendarPreview.issuer == issuer))
                session.flush()
                assert not session.scalar(select(Project.id).where(Project.issuer == issuer))
                assert not session.scalar(select(WorkTask.id).where(WorkTask.id.in_(tids)))
                assert not session.scalar(
                    select(CalendarVersion.id).where(CalendarVersion.issuer == issuer)
                )
                assert not session.scalar(
                    select(ScheduleChange.id).where(ScheduleChange.project_id.in_(pids))
                )
            with sessions() as session:
                for model in (ScheduleChange, SchedulePreview, DeliveryAssessment, DeliveryState):
                    assert not session.scalar(
                        select(model.project_id).where(model.project_id.in_(pids))
                    )
                for model in (TaskDependency, TaskSchedule, TaskChange, TaskAssignment):
                    assert not session.scalar(select(model.task_id).where(model.task_id.in_(tids)))
                assert not session.scalar(
                    select(CalendarPreview.id).where(CalendarPreview.issuer == issuer)
                )
            print(json.dumps({"kind": "cleanup", "verified": True}), flush=True)
        except Exception:
            failed = True
            print(json.dumps({"kind": "cleanup", "verified": False}), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
