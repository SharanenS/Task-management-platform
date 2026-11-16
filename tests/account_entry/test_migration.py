from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from people.models import Base
from sqlalchemy import create_engine, inspect


def test_initial_migration_matches_models_in_isolated_sqlite(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    database = tmp_path / "migration.sqlite"
    monkeypatch.setenv("PEOPLE_DATABASE_URL", "sqlite:///" + str(database))
    config = Config(str(root / "services/people/alembic.ini"))
    config.set_main_option("script_location", str(root / "services/people/migrations"))
    command.upgrade(config, "head")
    engine = create_engine("sqlite:///" + str(database))
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        assert {"accounts", "employee_profiles", "company_role_grants"}.issubset(
            inspect(connection).get_table_names()
        )
    command.downgrade(config, "base")
    with engine.connect() as connection:
        assert not {"accounts", "employee_profiles", "company_role_grants"}.intersection(
            inspect(connection).get_table_names()
        )
    engine.dispose()
