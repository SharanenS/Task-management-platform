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


def test_company_structure_backfills_existing_identity_without_replacement(tmp_path, monkeypatch):
    from uuid import uuid4

    import pytest
    from sqlalchemy import text

    root = Path(__file__).resolve().parents[2]
    database = tmp_path / "preserve.sqlite"
    url = "sqlite:///" + str(database)
    monkeypatch.setenv("PEOPLE_DATABASE_URL", url)
    config = Config(str(root / "services/people/alembic.ini"))
    config.set_main_option("script_location", str(root / "services/people/migrations"))
    command.upgrade(config, "0003_account_management")
    engine = create_engine(url)
    account, profile, subject = (str(uuid4()) for _ in range(3))
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO accounts (id,issuer,subject,active,version,created_at) VALUES (:id,'https://preserved.invalid',:subject,true,7,CURRENT_TIMESTAMP)"
            ),
            {"id": account, "subject": subject},
        )
        c.execute(
            text(
                "INSERT INTO employee_profiles (id,account_id,display_name,active) "
                "VALUES (:id,:account,'Preserved Person',true)"
            ),
            {"id": profile, "account": account},
        )
        c.execute(
            text("INSERT INTO company_role_grants (account_id,role) VALUES (:id,'ADMIN')"),
            {"id": account},
        )
    command.upgrade(config, "head")
    with engine.begin() as c:
        assert tuple(
            c.execute(
                text("SELECT id,account_id,issuer,display_name,version FROM employee_profiles")
            ).one()
        ) == (profile, account, "https://preserved.invalid", "Preserved Person", 1)
        assert tuple(c.execute(text("SELECT subject,version FROM accounts")).one()) == (subject, 7)
        assert c.scalar(text("SELECT role FROM company_role_grants")) == "ADMIN"
        c.execute(
            text(
                "INSERT INTO employee_profiles (id,issuer,display_name,active,version) VALUES (:id,'https://preserved.invalid','Unlinked',true,1)"
            ),
            {"id": str(uuid4())},
        )
    with pytest.raises(RuntimeError, match="Preserve unlinked"):
        command.downgrade(config, "0003_account_management")
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM employee_profiles")) == 2
    engine.dispose()
