from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from project_work.models import Base
from sqlalchemy import create_engine, inspect, text


def test_review_migration_preserves_schedule_schema_and_refuses_evidence_loss(
    tmp_path, monkeypatch
):
    root = Path(__file__).resolve().parents[2]
    url = "sqlite:///" + str(tmp_path / "reviews.sqlite")
    monkeypatch.setenv("PROJECT_WORK_DATABASE_URL", url)
    cfg = Config(str(root / "services/project-work/alembic.ini"))
    cfg.set_main_option("script_location", str(root / "services/project-work/migrations"))
    command.upgrade(cfg, "0007_task_scheduling")
    engine = create_engine(url)
    with engine.connect() as connection:
        previous = set(inspect(connection).get_table_names())
    command.upgrade(cfg, "head")
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    command.downgrade(cfg, "0007_task_scheduling")
    with engine.connect() as connection:
        assert set(inspect(connection).get_table_names()) == previous
    command.upgrade(cfg, "head")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO task_executions (task_id,progress,started_at) "
                "VALUES ('retained',0,'2026-01-01')"
            )
        )
    with pytest.raises(RuntimeError, match="Retained completion"):
        command.downgrade(cfg, "0007_task_scheduling")
