"""Approved runtime only: synthetic-issuer task races and exact owned cleanup."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from project_work.memberships import MembershipService
from project_work.models import (
    Base,
    CalendarPreview,
    CalendarVersion,
    DeliveryState,
    Project,
    ProjectMember,
    ProjectMembershipChange,
    ProjectPreview,
    TaskAssignment,
    TaskChange,
    WorkTask,
)
from project_work.projects import ProjectActor, ProjectError, ProjectService
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
    issuer = "https://s11-probe.invalid/" + run
    owner = ProjectActor(issuer, str(uuid4()), "ADMIN", "Probe owner")
    leader = ProjectActor(issuer, str(uuid4()), "EMPLOYEE", "Probe leader")
    employee = ProjectActor(issuer, str(uuid4()), "EMPLOYEE", "Probe employee")
    other = ProjectActor(issuer, str(uuid4()), "EMPLOYEE", "Probe other")
    actors = {owner.account_id, leader.account_id, employee.account_id, other.account_id}
    ids = []
    stage = "schema parity"
    failed = False

    def directory(values):
        return [
            {"account_id": v, "display_name": "Owned " + run, "role": "EMPLOYEE", "active": True}
            for v in values
            if v in actors - {owner.account_id}
        ]

    try:
        with engine.connect() as c:
            assert compare_metadata(MigrationContext.configure(c), Base.metadata) == []
        stage = "owned calendar and project"
        calendar = CalendarService(sessions)

        def authority():
            return issuer, owner.account_id

        config = {
            "timezone": "Asia/Colombo",
            "week": [
                {
                    "weekday": n,
                    "working": n <= 5,
                    "opens": "09:00" if n <= 5 else None,
                    "closes": "17:00" if n <= 5 else None,
                }
                for n in range(1, 8)
            ],
            "holidays": [],
            "exceptions": [],
        }
        # Use the same validated calendar shape as existing production publication.
        preview = calendar.preview(authority, config)
        calendar.publish(
            authority,
            {"request_id": str(uuid4()), "preview_id": preview["preview_id"], "confirm": True},
        )
        work = ProjectService(sessions)
        preview = work.preview(
            lambda: owner,
            {
                "name": "Owned S11 " + run,
                "objectives": "Owned concurrency probe",
                "deadline_date": "2030-01-07",
            },
        )
        project = work.create(
            lambda: owner,
            {"request_id": str(uuid4()), "preview_id": preview["preview_id"], "confirm": True},
        )
        ids = [project["id"]]
        members = MembershipService(sessions)
        for actor, role in ((leader, "LEADER"), (employee, "CONTRIBUTOR"), (other, "CONTRIBUTOR")):
            result = members.change(
                lambda: owner,
                lambda account_id: directory([account_id])[0],
                {
                    "project_id": project["id"],
                    "request_id": str(uuid4()),
                    "version": project["version"],
                    "account_id": actor.account_id,
                    "action": "appoint",
                    "responsibility": role,
                    "duties": "Owned " + run,
                    "confirm": True,
                },
            )
            project["version"] = result["version"]
        tasks = TaskService(sessions)
        value = {
            "project_id": project["id"],
            "project_version": project["version"],
            "request_id": str(uuid4()),
            "action": "CREATE",
            "task_id": None,
            "version": 0,
            "title": "Owned " + run,
            "instructions": "Owned " + run,
            "acceptance_criteria": "Owned " + run,
            "assignee_id": employee.account_id,
            "reason": "Owned " + run,
            "confirm": True,
        }
        stage = "creation and safe replay"
        created = tasks.change(lambda: leader, directory, value)
        assert tasks.change(lambda: leader, directory, value) == created
        stage = "competing assignment changes"
        barrier = Barrier(2)

        def race(target):
            command = {
                **value,
                "request_id": str(uuid4()),
                "project_version": created["project_version"],
                "task_id": created["task_id"],
                "version": created["version"],
                "action": "ASSIGN",
                "title": None,
                "instructions": None,
                "acceptance_criteria": None,
                "assignee_id": target,
            }
            barrier.wait(timeout=10)
            try:
                return ("won", tasks.change(lambda: leader, directory, command), command)
            except ProjectError as error:
                return (error.code, None, command)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(race, [leader.account_id, other.account_id]))
        assert sorted(r[0] for r in results) == ["stale_task", "won"]
        winner = next(r for r in results if r[0] == "won")
        assert tasks.change(lambda: leader, directory, winner[2]) == winner[1]
        stage = "retained assignment and private projection"
        with sessions() as s:
            rows = s.scalars(
                select(TaskAssignment).where(TaskAssignment.task_id == created["task_id"])
            ).all()
            assert len(rows) == 2 and sum(r.ended_at is None for r in rows) == 1
            assert (
                len(
                    s.scalars(
                        select(TaskChange).where(TaskChange.task_id == created["task_id"])
                    ).all()
                )
                == 2
            )
        assert tasks.workspace(lambda: employee, project["id"])["tasks"][0]["details"] is None
        assert (
            work.detail(lambda: owner, project["id"])["approved_deadline"]
            == project["approved_deadline"]
        )
    except Exception as error:
        failed = True
        print(
            json.dumps({"kind": "failure", "stage": stage, "type": type(error).__name__}),
            flush=True,
        )
    finally:
        try:
            with sessions() as s, s.begin():
                projects = s.scalars(select(Project).where(Project.issuer == issuer)).all()
                assert all(r.creator_id == owner.account_id and run in r.name for r in projects)
                ids = [r.id for r in projects]
                rows = s.scalars(select(WorkTask).where(WorkTask.project_id.in_(ids))).all()
                task_ids = [r.id for r in rows]
                assert all(r.creator_id == leader.account_id and run in r.title for r in rows)
                for model in (TaskChange, TaskAssignment):
                    rows = s.scalars(select(model).where(model.task_id.in_(task_ids))).all()
                    assert all(r.actor_id == leader.account_id for r in rows)
                    if model is TaskAssignment:
                        assert all(r.account_id in actors for r in rows)
                    s.execute(delete(model).where(model.task_id.in_(task_ids)))
                s.execute(delete(WorkTask).where(WorkTask.id.in_(task_ids)))
                s.execute(delete(DeliveryState).where(DeliveryState.project_id.in_(ids)))
                for row in s.scalars(select(ProjectMember).where(ProjectMember.issuer == issuer)):
                    assert row.project_id in ids and row.account_id in actors
                for row in s.scalars(
                    select(ProjectMembershipChange).where(ProjectMembershipChange.issuer == issuer)
                ):
                    assert (
                        row.project_id in ids
                        and row.actor_id == owner.account_id
                        and row.target_id in actors
                    )
                for model in (CalendarPreview, CalendarVersion, ProjectPreview):
                    assert all(
                        row.actor_id == owner.account_id
                        for row in s.scalars(select(model).where(model.issuer == issuer))
                    )
                for model in (ProjectMembershipChange, ProjectMember, Project, ProjectPreview):
                    s.execute(delete(model).where(model.issuer == issuer))
                for row in s.scalars(
                    select(CalendarPreview).where(CalendarPreview.issuer == issuer)
                ):
                    row.base_version_id = None
                s.flush()
                s.execute(delete(CalendarVersion).where(CalendarVersion.issuer == issuer))
                s.execute(delete(CalendarPreview).where(CalendarPreview.issuer == issuer))
            with sessions() as s:
                for model in (TaskChange, TaskAssignment):
                    assert not s.scalar(select(model.id).where(model.task_id.in_(task_ids)))
                assert not s.scalar(select(WorkTask.id).where(WorkTask.project_id.in_(ids)))
                for model in (
                    Project,
                    ProjectPreview,
                    ProjectMember,
                    ProjectMembershipChange,
                    CalendarPreview,
                    CalendarVersion,
                ):
                    assert not s.scalar(select(model.id).where(model.issuer == issuer))
            print(json.dumps({"kind": "cleanup", "verified": True}), flush=True)
        except Exception as error:
            failed = True
            print(
                json.dumps(
                    {"kind": "failure", "stage": "owned cleanup", "type": type(error).__name__}
                ),
                flush=True,
            )
        engine.dispose()
    if failed:
        return 1
    print(
        json.dumps(
            {
                "kind": "passed",
                "scope": "schema, assignment race, replay, private fields and owned cleanup",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
