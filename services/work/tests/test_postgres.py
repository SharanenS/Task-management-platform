import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Project, ProjectMembership, ProjectRole, Task, TaskPriority
from app.service import (
    Actor,
    WorkError,
    add_member,
    assign_task,
    create_project,
    create_task,
    remove_member,
    update_task,
)

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
        session.execute(delete(Task))
        session.execute(delete(ProjectMembership))
        session.execute(delete(Project))
        session.commit()
    yield factory
    with factory() as session:
        session.execute(delete(Task))
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


def test_project_lock_allocates_unique_concurrent_task_numbers(
    database: sessionmaker[Session],
) -> None:
    owner = Actor(uuid4(), "MANAGER")
    with database() as session:
        project_id = create_project(
            session, owner, key="PG-TASK-NUMBERS", name="Numbers", description=None
        ).id

    def create(index: int) -> int:
        with database() as session:
            return create_task(
                session,
                owner,
                project_id,
                title=f"Task {index}",
                description=None,
                priority=TaskPriority.MEDIUM,
                assignee_employee_id=None,
                due_date=None,
            ).number

    with ThreadPoolExecutor(max_workers=4) as executor:
        numbers = list(executor.map(create, range(8)))
    assert sorted(numbers) == list(range(1, 9))


def test_task_lock_rejects_one_competing_optimistic_update(
    database: sessionmaker[Session],
) -> None:
    owner = Actor(uuid4(), "MANAGER")
    with database() as session:
        project_id = create_project(
            session, owner, key="PG-TASK-VERSION", name="Version", description=None
        ).id
        task_id = create_task(
            session,
            owner,
            project_id,
            title="Original",
            description=None,
            priority=TaskPriority.MEDIUM,
            assignee_employee_id=None,
            due_date=None,
        ).id

    def update(title: str) -> str:
        with database() as session:
            try:
                update_task(
                    session,
                    owner,
                    project_id,
                    task_id,
                    title=title,
                    description=None,
                    priority=TaskPriority.HIGH,
                    due_date=None,
                    expected_version=1,
                )
                return "updated"
            except WorkError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(update, ["First", "Second"]))
    assert sorted(results) == ["VERSION_CONFLICT", "updated"]


def test_project_lock_prevents_assignment_membership_removal_race(
    database: sessionmaker[Session],
) -> None:
    owner = Actor(uuid4(), "MANAGER")
    target = uuid4()
    with database() as session:
        project = create_project(
            session, owner, key="PG-ASSIGNMENT-RACE", name="Assignment race", description=None
        )
        add_member(session, owner, project.id, target, ProjectRole.CONTRIBUTOR)
        task = create_task(
            session,
            owner,
            project.id,
            title="Race",
            description=None,
            priority=TaskPriority.MEDIUM,
            assignee_employee_id=None,
            due_date=None,
        )
        project_id, task_id = project.id, task.id

    ready = Barrier(2)

    def assign() -> str:
        with database() as session:
            ready.wait()
            try:
                assign_task(
                    session,
                    owner,
                    project_id,
                    task_id,
                    assignee_employee_id=target,
                    expected_version=1,
                )
                return "assigned"
            except WorkError as error:
                return error.code

    def remove() -> str:
        with database() as session:
            ready.wait()
            try:
                remove_member(session, owner, project_id, target)
                return "removed"
            except WorkError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assign_result = executor.submit(assign)
        remove_result = executor.submit(remove)
        results = {assign_result.result(), remove_result.result()}

    assert results in (
        {"assigned", "MEMBER_HAS_ASSIGNED_TASKS"},
        {"INVALID_ASSIGNEE", "removed"},
    )
    with database() as session:
        final_task = session.scalar(select(Task).where(Task.id == task_id))
        membership = session.scalar(
            select(ProjectMembership).where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.employee_id == target,
            )
        )
        assert final_task is not None
        assert final_task.assignee_employee_id is None or membership is not None
