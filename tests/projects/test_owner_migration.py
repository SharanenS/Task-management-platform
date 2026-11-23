from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from project_work.coordination import CoordinationService
from project_work.delivery_inputs import advance_schedule, open_escalation, record_assessment
from project_work.memberships import MembershipService
from project_work.models import Base
from project_work.owner_decisions import OwnerDecisionService
from project_work.projects import ProjectActor, ProjectService
from project_work.service import CalendarService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from working_calendar.test_calendar import config

from .test_domain import create
from .test_memberships import appointment, eligible
from .test_owner_decisions import NOW
from .test_owner_decisions import command as decision_command


def test_owner_migration_preserves_commitments_and_guards_new_history(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    url = "sqlite:///" + str(tmp_path / "owner.sqlite")
    monkeypatch.setenv("PROJECT_WORK_DATABASE_URL", url)
    cfg = Config(str(root / "services/project-work/alembic.ini"))
    cfg.set_main_option("script_location", str(root / "services/project-work/migrations"))
    command.upgrade(cfg, "0004_manager_coordination")
    engine = create_engine(url)
    sessions = sessionmaker(engine)
    owner = ProjectActor("https://owner-migration.invalid", str(uuid4()), "MANAGER", "Owner")

    def authority():
        return owner.issuer, owner.account_id

    calendar = CalendarService(sessions)
    preview = calendar.preview(authority, config())
    calendar.publish(
        authority,
        {"request_id": str(uuid4()), "preview_id": preview["preview_id"], "confirm": True},
    )
    work = ProjectService(sessions)
    project, _ = create(work, owner)
    member = str(uuid4())
    appointed = MembershipService(sessions).change(
        lambda: owner, eligible, appointment(project, member)
    )
    project["version"] = appointed["version"]
    coordination = CoordinationService(sessions)
    coordination.create(
        lambda: owner,
        eligible,
        {
            "project_id": project["id"],
            "request_id": str(uuid4()),
            "kind": "UPDATE",
            "topic": "Existing S9 request",
            "details": "Preserve prior coordination",
            "due_at": "2030-01-10T10:00:00Z",
            "location": "",
            "acknowledgement_required": True,
            "recipients": [member],
            "confirm": True,
        },
    )
    previous_coordination = coordination.workspace(lambda: owner, project["id"])
    command.upgrade(cfg, "head")
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    assert work.detail(lambda: owner, project["id"]) == project
    assert coordination.workspace(lambda: owner, project["id"]) == previous_coordination
    with sessions() as session, session.begin():
        advance_schedule(session, project["id"], 0)
        assessment = record_assessment(
            session,
            project["id"],
            1,
            project["version"],
            "ASSESSED",
            "2026-11-26T11:30:00Z",
            "Fixture assessment",
            now=NOW,
        )
        escalation = open_escalation(
            session, project["id"], str(uuid4()), assessment.id, "Request", "Delivery team"
        )
        escalation_id = escalation.id
    owners = OwnerDecisionService(sessions, lambda: NOW)
    owners.decide(lambda: owner, decision_command(project, escalation_id))
    with pytest.raises(RuntimeError, match="Preserve owner decisions"):
        command.downgrade(cfg, "0004_manager_coordination")
    assert len(owners.workspace(lambda: owner, project["id"])["history"]) == 1
    assert (
        work.detail(lambda: owner, project["id"])["approved_deadline"]
        == project["approved_deadline"]
    )
    engine.dispose()
