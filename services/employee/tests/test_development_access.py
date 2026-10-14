from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import development_access
from app.db import Base
from app.models import ApplicationRole, Employee


@pytest.fixture
def session_factory(monkeypatch: pytest.MonkeyPatch) -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(development_access, "SessionLocal", factory)
    return factory


def add_employee(factory: sessionmaker[Session], subject: str) -> None:
    with factory() as session:
        session.add(
            Employee(
                id=uuid4(),
                keycloak_subject=subject,
                email="acceptance@example.test",
                display_name="Acceptance User",
                role=ApplicationRole.MEMBER,
                active=True,
            )
        )
        session.commit()


def test_set_active_changes_existing_profile(
    session_factory: sessionmaker[Session],
) -> None:
    add_employee(session_factory, "inactive-subject")
    development_access.set_active(
        "inactive-subject", active=False, protected_subject="primary-subject"
    )

    with session_factory() as session:
        employee = session.scalar(
            select(Employee).where(Employee.keycloak_subject == "inactive-subject")
        )
        assert employee is not None
        assert employee.active is False


def test_remove_deletes_only_selected_profile(
    session_factory: sessionmaker[Session],
) -> None:
    add_employee(session_factory, "remove-subject")
    add_employee(session_factory, "keep-subject")
    development_access.remove("remove-subject", protected_subject="primary-subject")

    with session_factory() as session:
        subjects = set(session.scalars(select(Employee.keycloak_subject)))
        assert subjects == {"keep-subject"}


def test_refuses_to_modify_protected_primary_subject(
    session_factory: sessionmaker[Session],
) -> None:
    add_employee(session_factory, "primary-subject")

    with pytest.raises(SystemExit, match="protected primary"):
        development_access.set_active(
            "primary-subject", active=False, protected_subject="primary-subject"
        )


def test_refuses_to_run_outside_development_or_test(
    session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    add_employee(session_factory, "disposable-subject")
    monkeypatch.setattr(development_access.settings, "app_env", "production")

    with pytest.raises(SystemExit, match="disabled in this environment"):
        development_access.remove("disposable-subject", protected_subject="primary-subject")
