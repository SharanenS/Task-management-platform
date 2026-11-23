"""Approved runtime only: synthetic-issuer S10 races and verified owned cleanup."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from project_work.delivery_inputs import advance_schedule, open_escalation, record_assessment
from project_work.memberships import MembershipService
from project_work.models import (
    Base,
    CalendarPreview,
    CalendarVersion,
    DeliveryAssessment,
    DeliveryState,
    OwnerDecision,
    OwnerDecisionPreview,
    OwnerEscalation,
    Project,
    ProjectMember,
    ProjectMembershipChange,
    ProjectPreview,
    ReviewFallback,
)
from project_work.owner_decisions import OwnerDecisionService
from project_work.projects import ProjectActor, ProjectError, ProjectService
from project_work.review_fallbacks import ReviewFallbackService
from project_work.service import CalendarService
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker


def main():
    engine = create_engine(os.environ["PROJECT_WORK_DATABASE_URL"], hide_parameters=True)
    if engine.url.host != "project-work-db" or engine.url.database != "taskspace_project_work":
        raise ValueError("Wrong project-work database")
    sessions = sessionmaker(engine)
    run, owner_id, leader_id = (str(uuid4()) for _ in range(3))
    issuer = "https://owner-probe.invalid/" + run
    actor = ProjectActor(issuer, owner_id, "MANAGER", "Owned S10 probe " + run)

    def authority():
        return actor

    def calendar_authority():
        return issuer, owner_id

    def eligible(account):
        assert account == leader_id
        return {
            "account_id": account,
            "active": True,
            "role": "EMPLOYEE",
            "display_name": "Owned leader " + run,
        }

    stage, failed = "schema parity", False
    try:
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        stage = "owned calendar, project and leader"
        calendar = CalendarService(sessions)
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
        preview = calendar.preview(calendar_authority, config)
        calendar.publish(
            calendar_authority,
            {"request_id": str(uuid4()), "preview_id": preview["preview_id"], "confirm": True},
        )
        projects = ProjectService(sessions)
        preview = projects.preview(
            authority,
            {"name": "Owned S10 " + run, "objectives": "Race proof", "deadline_date": "2030-01-07"},
        )
        project = projects.create(
            authority,
            {"request_id": str(uuid4()), "preview_id": preview["preview_id"], "confirm": True},
        )
        membership = MembershipService(sessions).change(
            authority,
            eligible,
            {
                "project_id": project["id"],
                "account_id": leader_id,
                "version": 1,
                "request_id": str(uuid4()),
                "action": "appoint",
                "responsibility": "LEADER",
                "duties": "Owned leader " + run,
                "confirm": True,
            },
        )
        with sessions() as session, session.begin():
            advance_schedule(session, project["id"], 0)
            assessment = record_assessment(
                session,
                project["id"],
                1,
                membership["version"],
                "ASSESSED",
                "2030-01-09T17:00:00Z",
                "Owned S10 assessment " + run,
            )
            escalation = open_escalation(
                session,
                project["id"],
                str(uuid4()),
                assessment.id,
                "Owned S10 request " + run,
                "Owned team " + run,
            )
            escalation_id = escalation.id
        owners = OwnerDecisionService(sessions)
        preview = owners.preview(
            authority,
            {
                "project_id": project["id"],
                "escalation_id": escalation_id,
                "version": 1,
                "deadline_date": "2030-01-10",
            },
        )
        value = {
            "project_id": project["id"],
            "escalation_id": escalation_id,
            "request_id": str(uuid4()),
            "version": 1,
            "project_version": membership["version"],
            "outcome": "REVISE_DEADLINE",
            "reason": "Owned S10 decision " + run,
            "affected_team": "Owned team " + run,
            "preview_id": preview["id"],
            "confirm": True,
        }
        commands = [value, {**value, "request_id": str(uuid4())}]
        stage = "competing owner decisions"
        barrier = Barrier(2)

        def compete(command):
            barrier.wait()
            try:
                return owners.decide(authority, command)
            except ProjectError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(compete, commands))
        assert sum(isinstance(result, dict) for result in outcomes) == 1
        assert outcomes.count("stale_owner_escalation") == 1
        winner = next(i for i, result in enumerate(outcomes) if isinstance(result, dict))
        assert owners.decide(authority, commands[winner]) == outcomes[winner]
        state = owners.workspace(authority, project["id"])
        assert len(state["history"]) == 1 and state["escalations"] == []
        assert state["project"]["approved_deadline"] == project["approved_deadline"]
        assert (
            state["current_deadline"] == preview["deadline_at"]
            and state["actual_delivery_at"] is None
        )
        stage = "explicit scoped fallback and revocation"
        fallbacks = ReviewFallbackService(sessions, {"ADMIN", "MANAGER"})
        now = datetime.now(UTC)
        record = fallbacks.create(
            authority,
            {
                "project_id": project["id"],
                "project_version": state["project"]["version"],
                "request_id": str(uuid4()),
                "leader_id": leader_id,
                "scope": "REVIEWS",
                "reason": "Owned absence " + run,
                "starts_at": (now - timedelta(minutes=1)).isoformat(),
                "ends_at": (now + timedelta(hours=1)).isoformat(),
                "confirm": True,
            },
        )
        with sessions() as session, session.begin():
            proof = fallbacks.require_in_transaction(session, authority, project["id"], "REVIEWS")
            assert proof["actor_id"] == owner_id and proof["record_id"] == record["id"]
        revoked = fallbacks.revoke(
            authority,
            {
                "project_id": project["id"],
                "record_id": record["id"],
                "request_id": str(uuid4()),
                "reason": "Owned revocation " + run,
                "confirm": True,
            },
        )
        assert not revoked["active"]
    except Exception as error:
        failed = True
        print(
            json.dumps({"kind": "failure", "stage": stage, "type": type(error).__name__}),
            flush=True,
        )
    finally:
        try:
            with sessions() as session, session.begin():
                projects_owned = session.scalars(
                    select(Project).where(Project.issuer == issuer)
                ).all()
                ids = [row.id for row in projects_owned]
                assert all(
                    row.creator_id == row.owner_id == owner_id and run in row.name
                    for row in projects_owned
                )
                for model in (
                    OwnerDecision,
                    OwnerDecisionPreview,
                    OwnerEscalation,
                    DeliveryAssessment,
                    DeliveryState,
                    ReviewFallback,
                ):
                    rows = session.scalars(select(model).where(model.project_id.in_(ids))).all()
                    if model in {OwnerDecision, OwnerDecisionPreview, ReviewFallback}:
                        assert all(row.actor_id == owner_id for row in rows)
                    if model is DeliveryAssessment:
                        assert all(run in row.summary for row in rows)
                    if model is OwnerEscalation:
                        assert all(run in row.reason for row in rows)
                    if model is ReviewFallback:
                        assert all(
                            row.leader_id == leader_id and row.revoked_by in {None, owner_id}
                            for row in rows
                        )
                    session.execute(delete(model).where(model.project_id.in_(ids)))
                members = session.scalars(
                    select(ProjectMember).where(ProjectMember.issuer == issuer)
                ).all()
                changes = session.scalars(
                    select(ProjectMembershipChange).where(ProjectMembershipChange.issuer == issuer)
                ).all()
                assert all(row.project_id in ids and row.account_id == leader_id for row in members)
                assert all(
                    row.project_id in ids
                    and row.actor_id == owner_id
                    and row.target_id == leader_id
                    for row in changes
                )
                for model in (ProjectPreview, CalendarPreview, CalendarVersion):
                    assert all(
                        row.actor_id == owner_id
                        for row in session.scalars(select(model).where(model.issuer == issuer))
                    )
                for model in (ProjectMembershipChange, ProjectMember, Project, ProjectPreview):
                    session.execute(delete(model).where(model.issuer == issuer))
                for row in session.scalars(
                    select(CalendarPreview).where(CalendarPreview.issuer == issuer)
                ):
                    row.base_version_id = None
                session.flush()
                session.execute(delete(CalendarVersion).where(CalendarVersion.issuer == issuer))
                session.execute(delete(CalendarPreview).where(CalendarPreview.issuer == issuer))
            with sessions() as session:
                for model in (
                    OwnerDecision,
                    OwnerDecisionPreview,
                    OwnerEscalation,
                    DeliveryAssessment,
                    DeliveryState,
                    ReviewFallback,
                ):
                    assert not session.scalar(
                        select(model.project_id).where(model.project_id.in_(ids))
                    )
                for model in (
                    ProjectMembershipChange,
                    ProjectMember,
                    Project,
                    ProjectPreview,
                    CalendarVersion,
                    CalendarPreview,
                ):
                    assert not session.scalar(select(model.id).where(model.issuer == issuer))
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
                "scope": "schema, decision races, replay, baseline, fallback and owned cleanup",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
