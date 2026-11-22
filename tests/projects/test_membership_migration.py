from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from project_work.memberships import MembershipService
from project_work.models import Base
from project_work.projects import ProjectActor, ProjectService
from project_work.service import CalendarService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from working_calendar.test_calendar import config

from .test_domain import create
from .test_memberships import appointment, eligible


def test_membership_migration_preserves_commitments_and_guards_history(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    url = "sqlite:///" + str(tmp_path / "memberships.sqlite")
    monkeypatch.setenv("PROJECT_WORK_DATABASE_URL", url)
    cfg = Config(str(root / "services/project-work/alembic.ini"))
    cfg.set_main_option("script_location", str(root / "services/project-work/migrations"))
    command.upgrade(cfg, "0002_manager_projects")
    engine = create_engine(url)
    sessions = sessionmaker(engine)
    owner = ProjectActor("https://migration.invalid", str(uuid4()), "MANAGER", "Owner")

    def authority():
        return owner.issuer, owner.account_id

    calendar = CalendarService(sessions)
    preview = calendar.preview(authority, config())
    version = calendar.publish(
        authority,
        {"request_id": str(uuid4()), "preview_id": preview["preview_id"], "confirm": True},
    )
    projects = ProjectService(sessions)
    project, _ = create(projects, owner)
    command.upgrade(cfg, "head")
    assert projects.detail(lambda: owner, project["id"]) == project
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    members = MembershipService(sessions)
    members.change(
        lambda: owner, eligible, appointment(project, str(uuid4()), responsibility="LEADER")
    )
    with pytest.raises(RuntimeError, match="Preserve membership history"):
        command.downgrade(cfg, "0002_manager_projects")
    view = members.workspace(lambda: owner, project["id"])
    assert len(view["history"]) == 1
    assert view["project"]["approved_deadline"] == project["approved_deadline"]
    assert calendar.workspace(authority)["current"]["id"] == version["id"]
    engine.dispose()
