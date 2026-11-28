from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from project_work.models import Base
from sqlalchemy import create_engine, inspect, text


def test_schedule_migration_matches_metadata_and_empty_rollback(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    url = "sqlite:///" + str(tmp_path / "schedule.sqlite")
    monkeypatch.setenv("PROJECT_WORK_DATABASE_URL", url)
    cfg = Config(str(root / "services/project-work/alembic.ini"))
    cfg.set_main_option("script_location", str(root / "services/project-work/migrations"))
    command.upgrade(cfg, "0006_task_breakdown")
    engine = create_engine(url)
    with engine.connect() as connection:
        previous = set(inspect(connection).get_table_names())
    command.upgrade(cfg, "head")
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    command.downgrade(cfg, "0006_task_breakdown")
    with engine.connect() as connection:
        assert set(inspect(connection).get_table_names()) == previous
    command.upgrade(cfg, "head")
    with engine.begin() as connection:
        # A retained preview is evidence even when no schedule was committed.
        connection.execute(
            text(
                "INSERT INTO task_schedule_previews "
                "(id,project_id,actor_id,project_version,source_hash,payload,result,"
                "created_at,valid_until) VALUES "
                "('preview','project','actor',1,'hash','{}','{}','2026-01-01','2026-01-02')"
            )
        )
    with pytest.raises(RuntimeError, match="Retained scheduling"):
        command.downgrade(cfg, "0006_task_breakdown")
