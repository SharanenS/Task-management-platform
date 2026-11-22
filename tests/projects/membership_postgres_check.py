"""Approved-runtime probe: synthetic-issuer membership races and owned cleanup."""

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
    Project,
    ProjectMember,
    ProjectMembershipChange,
    ProjectPreview,
)
from project_work.projects import ProjectActor, ProjectError, ProjectService
from project_work.service import CalendarService
from sqlalchemy import create_engine, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker


def main():
    engine = create_engine(os.environ["PROJECT_WORK_DATABASE_URL"], hide_parameters=True)
    if engine.url.host != "project-work-db" or engine.url.database != "taskspace_project_work":
        raise ValueError("Wrong work database")
    sessions = sessionmaker(engine)
    run = str(uuid4())
    issuer = "https://membership-probe.invalid/" + run
    owner_id, first, second = (str(uuid4()) for _ in range(3))
    actor = ProjectActor(issuer, owner_id, "MANAGER", "Owned membership probe")
    service = MembershipService(sessions)
    projects = ProjectService(sessions)

    def authority():
        return actor

    def calendar_authority():
        return issuer, owner_id

    targets = {first, second}

    def eligible(account):
        assert account in targets
        return {
            "account_id": account,
            "active": True,
            "role": "EMPLOYEE",
            "display_name": "Owned probe " + run,
        }

    stage = "schema parity"
    failed = False
    try:
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        stage = "owned calendar and project"
        calendars = CalendarService(sessions)
        config = {
            "timezone": "Etc/UTC",
            "week": [
                {
                    "weekday": i,
                    "working": i <= 5,
                    "opens": "09:00" if i <= 5 else None,
                    "closes": "17:00" if i <= 5 else None,
                }
                for i in range(1, 8)
            ],
            "holidays": [],
            "exceptions": [],
        }
        preview = calendars.preview(calendar_authority, config)
        calendars.publish(
            calendar_authority,
            {"request_id": str(uuid4()), "preview_id": preview["preview_id"], "confirm": True},
        )
        preview = projects.preview(
            authority,
            {
                "name": "Owned membership " + run,
                "objectives": "Synthetic race",
                "deadline_date": "2030-01-07",
            },
        )
        project = projects.create(
            authority,
            {"request_id": str(uuid4()), "preview_id": preview["preview_id"], "confirm": True},
        )
        requests = [
            {
                "project_id": project["id"],
                "account_id": target,
                "version": 1,
                "request_id": str(uuid4()),
                "action": "appoint",
                "responsibility": "LEADER",
                "duties": "Owned " + run,
                "confirm": True,
            }
            for target in (first, second)
        ]
        stage = "competing leader appointments"
        barrier = Barrier(2)

        def appoint(index):
            barrier.wait(timeout=5)
            try:
                return service.change(authority, eligible, requests[index])
            except ProjectError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(appoint, [0, 1]))
        assert results.count("stale_project_membership") == 1
        winner = next(i for i, value in enumerate(results) if isinstance(value, dict))
        stage = "safe replay and one retained audit"
        assert service.change(authority, eligible, requests[winner]) == results[winner]
        with sessions() as s:
            rows = s.scalars(
                select(ProjectMember).where(ProjectMember.project_id == project["id"])
            ).all()
            history = s.scalars(
                select(ProjectMembershipChange).where(
                    ProjectMembershipChange.project_id == project["id"]
                )
            ).all()
            assert len(rows) == len(history) == 1 and rows[0].responsibility == "LEADER"
        stage = "database leader uniqueness"
        try:
            with sessions() as s, s.begin():
                s.add(
                    ProjectMember(
                        issuer=issuer,
                        project_id=project["id"],
                        account_id=requests[1 - winner]["account_id"],
                        display_name="Owned probe " + run,
                        responsibility="LEADER",
                        duties="Owned " + run,
                        active=True,
                    )
                )
                s.flush()
            raise AssertionError("Leader constraint not enforced")
        except IntegrityError:
            pass
        stage = "revocation history and immutable project deadline"
        service.change(
            authority,
            eligible,
            {**requests[winner], "version": 2, "request_id": str(uuid4()), "action": "remove"},
        )
        assert (
            projects.detail(authority, project["id"])["approved_deadline"]
            == project["approved_deadline"]
        )
        assert len(service.workspace(authority, project["id"])["history"]) == 2
    except Exception as error:
        failed = True
        print(
            json.dumps({"kind": "failure", "stage": stage, "type": type(error).__name__}),
            flush=True,
        )
    finally:
        try:
            with sessions() as s, s.begin():
                owned_projects = s.scalars(select(Project).where(Project.issuer == issuer)).all()
                pids = [r.id for r in owned_projects]
                members = s.scalars(
                    select(ProjectMember).where(
                        (ProjectMember.issuer == issuer) | ProjectMember.project_id.in_(pids)
                    )
                ).all()
                changes = s.scalars(
                    select(ProjectMembershipChange).where(
                        (ProjectMembershipChange.issuer == issuer)
                        | ProjectMembershipChange.project_id.in_(pids)
                    )
                ).all()
                assert all(
                    r.creator_id == owner_id and r.owner_id == owner_id and run in r.name
                    for r in owned_projects
                )
                assert all(
                    r.issuer == issuer and r.project_id in pids and r.account_id in targets
                    for r in members
                )
                assert all(
                    r.issuer == issuer
                    and r.project_id in pids
                    and r.actor_id == owner_id
                    and r.target_id in targets
                    for r in changes
                )
                for model in (ProjectPreview, CalendarPreview, CalendarVersion):
                    assert all(
                        r.actor_id == owner_id
                        for r in s.scalars(select(model).where(model.issuer == issuer))
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
                for model in (
                    ProjectMembershipChange,
                    ProjectMember,
                    Project,
                    ProjectPreview,
                    CalendarVersion,
                    CalendarPreview,
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
                "scope": "schema, competing leaders, replay, audit, revocation and owned cleanup",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
