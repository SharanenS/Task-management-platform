from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from project_work.delivery_inputs import open_escalation
from project_work.memberships import MembershipService
from project_work.models import Base
from project_work.owner_decisions import OwnerDecisionService
from project_work.projects import ProjectActor, ProjectService
from project_work.service import CalendarService
from project_work.tasks import TaskService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from working_calendar.test_calendar import config

from .test_domain import create
from .test_memberships import appointment, eligible
from .test_owner_decisions import command as owner_command
from .test_tasks import change, directory


def test_s11_upgrade_preserves_owner_history_and_blocks_destructive_downgrade(
    tmp_path, monkeypatch
):
    root = Path(__file__).resolve().parents[2]
    url = "sqlite:///" + str(tmp_path / "tasks.sqlite")
    monkeypatch.setenv("PROJECT_WORK_DATABASE_URL", url)
    cfg = Config(str(root / "services/project-work/alembic.ini"))
    cfg.set_main_option("script_location", str(root / "services/project-work/migrations"))
    command.upgrade(cfg, "0005_owner_decisions")
    engine = create_engine(url)
    sessions = sessionmaker(engine)
    owner = ProjectActor("https://migration.invalid", str(uuid4()), "ADMIN", "Owner")
    calendar = CalendarService(sessions)

    def authority():
        return owner.issuer, owner.account_id

    preview = calendar.preview(authority, config())
    calendar.publish(
        authority,
        {"request_id": str(uuid4()), "preview_id": preview["preview_id"], "confirm": True},
    )
    work = ProjectService(sessions)
    project, _ = create(work, owner)
    with sessions() as s, s.begin():
        row = open_escalation(s, project["id"], str(uuid4()), None, "Needs a plan", "Team")
        escalation_id = row.id
    owners = OwnerDecisionService(sessions)
    owners.decide(lambda: owner, owner_command(project, escalation_id, outcome="REQUEST_REPLAN"))
    previous = owners.workspace(lambda: owner, project["id"])
    command.upgrade(cfg, "head")
    with engine.connect() as c:
        assert compare_metadata(MigrationContext.configure(c), Base.metadata) == []
    assert owners.workspace(lambda: owner, project["id"]) == previous
    leader = ProjectActor(owner.issuer, str(uuid4()), "EMPLOYEE", "Leader")
    project = work.detail(lambda: owner, project["id"])
    project["version"] = MembershipService(sessions).change(
        lambda: owner, eligible, appointment(project, leader.account_id, responsibility="LEADER")
    )["version"]
    TaskService(sessions).change(lambda: leader, directory, change(project, leader))
    with pytest.raises(RuntimeError, match="Retained task history"):
        command.downgrade(cfg, "0005_owner_decisions")
    assert len(TaskService(sessions).workspace(lambda: leader, project["id"])["tasks"]) == 1
    engine.dispose()
