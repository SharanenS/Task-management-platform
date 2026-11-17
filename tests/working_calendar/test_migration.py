from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from project_work.models import Base
from sqlalchemy import create_engine


def test_calendar_migration_matches_owned_schema_and_empty_downgrade(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    url = "sqlite:///" + str(tmp_path / "calendar.sqlite")
    monkeypatch.setenv("PROJECT_WORK_DATABASE_URL", url)
    config = Config(str(root / "services/project-work/alembic.ini"))
    config.set_main_option("script_location", str(root / "services/project-work/migrations"))
    command.upgrade(config, "head")
    engine = create_engine(url)
    with engine.connect() as c:
        assert compare_metadata(MigrationContext.configure(c), Base.metadata) == []
    command.downgrade(config, "base")
    engine.dispose()
