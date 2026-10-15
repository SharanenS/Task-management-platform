import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session, sessionmaker

from app.models import Project, ProjectMembership, ProjectRole
from app.service import Actor, WorkError, add_member, create_project, remove_member

DATABASE_URL = os.getenv("WORK_POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="WORK_POSTGRES_TEST_URL is required for PostgreSQL integration tests."
)


@pytest.fixture
def database() -> sessionmaker[Session]:
    assert DATABASE_URL
    engine = create_engine(DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.execute(delete(ProjectMembership))
        session.execute(delete(Project))
        session.commit()
    yield factory
    with factory() as session:
        session.execute(delete(ProjectMembership))
        session.execute(delete(Project))
        session.commit()
    engine.dispose()


def test_concurrent_duplicate_membership_has_one_sanitized_conflict(
    database: sessionmaker[Session],
) -> None:
    owner = Actor(uuid4(), "MANAGER")
    target = uuid4()
    with database() as session:
        project_id = create_project(
            session, owner, key="PG-DUPLICATE", name="Duplicate", description=None
        ).id

    def attempt() -> str:
        with database() as session:
            try:
                add_member(session, owner, project_id, target, ProjectRole.CONTRIBUTOR)
                return "created"
            except WorkError as error:
                assert error.message == "The employee is already a member."
                return error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: attempt(), range(2)))
    assert sorted(results) == ["MEMBERSHIP_CONFLICT", "created"]


def test_project_lock_serializes_competing_final_manager_removals(
    database: sessionmaker[Session],
) -> None:
    first = Actor(uuid4(), "MANAGER")
    second_id = uuid4()
    with database() as session:
        project = create_project(
            session, first, key="PG-MANAGERS", name="Managers", description=None
        )
        add_member(
            session,
            first,
            project.id,
            second_id,
            ProjectRole.PROJECT_MANAGER,
        )
        project_id = project.id

    def remove(target_id: object) -> str:
        with database() as session:
            try:
                remove_member(session, Actor(uuid4(), "ADMIN"), project_id, target_id)  # type: ignore[arg-type]
                return "removed"
            except WorkError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(remove, [first.employee_id, second_id]))
    assert sorted(results) == ["FINAL_PROJECT_MANAGER", "removed"]
    with database() as session:
        remaining = session.query(ProjectMembership).filter_by(project_id=project_id).all()
        assert len(remaining) == 1
        assert remaining[0].role == ProjectRole.PROJECT_MANAGER
