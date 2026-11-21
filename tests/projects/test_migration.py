from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from project_work.models import CalendarVersion, Project
from project_work.projects import ProjectActor, ProjectService
from project_work.service import CalendarService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from working_calendar.test_calendar import config


def test_project_migration_preserves_published_calendars_and_guards_commitments(
    tmp_path, monkeypatch
):
    root = Path(__file__).resolve().parents[2]
    url = "sqlite:///" + str(tmp_path / "projects.sqlite")
    monkeypatch.setenv("PROJECT_WORK_DATABASE_URL", url)
    cfg = Config(str(root / "services/project-work/alembic.ini"))
    cfg.set_main_option("script_location", str(root / "services/project-work/migrations"))
    command.upgrade(cfg, "0001_company_calendar")
    engine = create_engine(url)
    sessions = sessionmaker(engine)
    issuer = "https://migration.invalid"
    account = str(uuid4())

    def authority():
        return issuer, account

    calendars = CalendarService(sessions)
    preview = calendars.preview(authority, config())
    version = calendars.publish(
        authority,
        {"request_id": str(uuid4()), "preview_id": preview["preview_id"], "confirm": True},
    )
    before = calendars.calculation(
        authority, {"version_id": version["id"], "start": "2026-11-20", "duration": 3}
    )
    command.upgrade(cfg, "head")
    assert (
        calendars.calculation(
            authority, {"version_id": version["id"], "start": "2026-11-20", "duration": 3}
        )
        == before
    )
    projects = ProjectService(sessions)
    actor = ProjectActor(issuer, account, "MANAGER", "Migration fixture")
    preview = projects.preview(
        lambda: actor,
        {"name": "Preserved project", "objectives": "Commitment", "deadline_date": "2026-11-24"},
    )
    project = projects.create(
        lambda: actor,
        {"request_id": str(uuid4()), "preview_id": preview["preview_id"], "confirm": True},
    )
    with pytest.raises(RuntimeError, match="Preserve project commitments"):
        command.downgrade(cfg, "0001_company_calendar")
    with sessions() as s:
        assert (
            s.get(CalendarVersion, version["id"]) is not None
            and s.get(Project, project["id"]) is not None
        )
    engine.dispose()
