"""Approved-runtime probe: synthetic-issuer coordination races and owned cleanup."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from project_work.coordination import CoordinationService
from project_work.memberships import MembershipService
from project_work.models import (
    Base,
    CalendarPreview,
    CalendarVersion,
    CoordinationFollowUp,
    CoordinationRecipient,
    CoordinationRecord,
    Project,
    ProjectMember,
    ProjectMembershipChange,
    ProjectPreview,
)
from project_work.projects import ProjectActor, ProjectError, ProjectService
from project_work.service import CalendarService
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker


def main():
    engine = create_engine(os.environ["PROJECT_WORK_DATABASE_URL"], hide_parameters=True)
    if engine.url.host != "project-work-db" or engine.url.database != "taskspace_project_work":
        raise ValueError("Wrong work database")
    sessions = sessionmaker(engine)
    run = str(uuid4())
    issuer = "https://coordination-probe.invalid/" + run
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
        stage = "owned recipient appointment"
        service.change(
            authority,
            eligible,
            {
                "project_id": project["id"],
                "account_id": first,
                "version": 1,
                "request_id": str(uuid4()),
                "action": "appoint",
                "responsibility": "LEADER",
                "duties": "Owned coordination probe",
                "confirm": True,
            },
        )
        coordination = CoordinationService(sessions)
        request = {
            "project_id": project["id"],
            "request_id": str(uuid4()),
            "kind": "UPDATE",
            "topic": "Owned coordination " + run,
            "details": "Synthetic concurrency proof",
            "due_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "location": "",
            "recipients": [first],
            "acknowledgement_required": True,
            "confirm": True,
        }
        stage = "idempotent creation"
        record = coordination.create(authority, eligible, request)
        assert coordination.create(authority, eligible, request) == record
        follow = {
            "project_id": project["id"],
            "record_id": record["id"],
            "request_id": str(uuid4()),
            "version": 1,
            "note": "Owned follow-up " + run,
            "next_follow_up_at": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
            "confirm": True,
        }
        stage = "concurrent follow-ups"
        barrier = Barrier(2)
        commands = [follow, {**follow, "request_id": str(uuid4())}]

        def compete(command):
            barrier.wait()
            try:
                return coordination.follow_up(authority, command)
            except ProjectError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(compete, commands))
        assert sum(isinstance(value, dict) for value in outcomes) == 1
        assert outcomes.count("coordination_stale") == 1
        winner = next(i for i, value in enumerate(outcomes) if isinstance(value, dict))
        stage = "replay, immutable deadline and pending response"
        updated = coordination.follow_up(authority, commands[winner])
        assert updated["due_at"] == record["due_at"] and updated["version"] == 2
        assert len(updated["follow_ups"]) == 1
        assert updated["recipients"][0]["response_state"] == "PENDING"
        assert (
            projects.detail(authority, project["id"])["approved_deadline"]
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
                records = s.scalars(
                    select(CoordinationRecord).where(CoordinationRecord.issuer == issuer)
                ).all()
                record_ids = [r.id for r in records]
                assert all(
                    r.project_id in pids and r.actor_id == owner_id and run in r.topic
                    for r in records
                )
                recipients = s.scalars(
                    select(CoordinationRecipient).where(
                        CoordinationRecipient.record_id.in_(record_ids)
                    )
                ).all()
                follows = s.scalars(
                    select(CoordinationFollowUp).where(
                        CoordinationFollowUp.record_id.in_(record_ids)
                    )
                ).all()
                assert all(r.account_id in targets for r in recipients)
                assert all(r.actor_id == owner_id and run in r.note for r in follows)
                s.execute(
                    delete(CoordinationFollowUp).where(
                        CoordinationFollowUp.id.in_([r.id for r in follows])
                    )
                )
                s.execute(
                    delete(CoordinationRecipient).where(
                        CoordinationRecipient.id.in_([r.id for r in recipients])
                    )
                )
                s.execute(delete(CoordinationRecord).where(CoordinationRecord.id.in_(record_ids)))
                s.flush()
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
                assert not s.scalar(
                    select(CoordinationRecipient.id).where(
                        CoordinationRecipient.record_id.in_(record_ids)
                    )
                )
                assert not s.scalar(
                    select(CoordinationFollowUp.id).where(
                        CoordinationFollowUp.record_id.in_(record_ids)
                    )
                )
                assert not s.scalar(
                    select(CoordinationRecord.id).where(CoordinationRecord.issuer == issuer)
                )
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
                "scope": "schema, competing follow-ups, replay, deadlines and owned cleanup",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
