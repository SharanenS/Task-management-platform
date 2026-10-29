import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.event_publisher import claim_events, settle_failure, settle_success
from app.models import (
    Project,
    ProjectMembership,
    ProjectRole,
    Task,
    TaskActivity,
    TaskPriority,
    TaskStatus,
    WorkEventStatus,
    WorkOutboxEvent,
)
from app.service import (
    Actor,
    WorkError,
    add_member,
    assign_task,
    change_task_status,
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
        session.execute(delete(WorkOutboxEvent))
        session.execute(delete(Task))
        session.execute(delete(ProjectMembership))
        session.execute(delete(Project))
        session.commit()
    yield factory
    with factory() as session:
        session.execute(delete(WorkOutboxEvent))
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


def test_concurrent_completion_commits_one_task_transition_and_one_outbox_event(
    database: sessionmaker[Session],
) -> None:
    owner = Actor(uuid4(), "MANAGER")
    with database() as session:
        project_id = create_project(
            session, owner, key="PG-WORKFLOW", name="Workflow", description=None
        ).id
        task = create_task(
            session,
            owner,
            project_id,
            title="Complete once",
            description=None,
            priority=TaskPriority.MEDIUM,
            assignee_employee_id=None,
            due_date=None,
        )
        change_task_status(
            session, owner, project_id, task.id, status=TaskStatus.IN_PROGRESS, expected_version=1
        )
        task_id = task.id

    def complete(_: int) -> str:
        with database() as session:
            try:
                change_task_status(
                    session, owner, project_id, task_id, status=TaskStatus.DONE, expected_version=2
                )
                return "completed"
            except WorkError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(complete, range(2)))
    assert sorted(results) == ["VERSION_CONFLICT", "completed"]
    with database() as session:
        task = session.get(Task, task_id)
        events = list(
            session.scalars(select(WorkOutboxEvent).where(WorkOutboxEvent.task_id == task_id))
        )
        assert task and task.status == TaskStatus.DONE
        assert len(events) == 1 and events[0].task_version == task.version


def _outbox(task_number: int, created_at: datetime) -> WorkOutboxEvent:
    return WorkOutboxEvent(
        event_type="TASK_COMPLETED",
        schema_version=1,
        project_id=uuid4(),
        task_id=uuid4(),
        actor_employee_id=uuid4(),
        task_version=task_number,
        created_at=created_at,
        available_at=created_at,
    )


def test_publishers_claim_disjoint_bounded_ordered_batches(database: sessionmaker[Session]) -> None:
    now = datetime.now(UTC)
    with database() as session:
        session.add_all([_outbox(index, now + timedelta(microseconds=index)) for index in range(6)])
        session.commit()
    barrier = Barrier(2)

    def claim(_: int) -> list[tuple[object, int]]:
        with database() as session:
            barrier.wait()
            return [
                (item.id, item.task_version)
                for item in claim_events(session, now=now + timedelta(seconds=1), limit=3)
            ]

    with ThreadPoolExecutor(max_workers=2) as executor:
        batches = list(executor.map(claim, range(2)))
    assert all(len(batch) <= 3 for batch in batches)
    assert set(item[0] for item in batches[0]).isdisjoint(item[0] for item in batches[1])
    assert sorted(item[1] for batch in batches for item in batch) == list(range(6))
    assert all(
        [item[1] for item in batch] == sorted(item[1] for item in batch) for batch in batches
    )


def test_expired_lease_reclaim_is_single_owner_and_exact_token_fenced(
    database: sessionmaker[Session],
) -> None:
    now = datetime.now(UTC)
    with database() as session:
        item = _outbox(1, now - timedelta(minutes=2))
        item.status = WorkEventStatus.IN_FLIGHT
        item.lease_token = "previous-token"
        item.lease_expires_at = now - timedelta(seconds=1)
        session.add(item)
        session.commit()
        event_id = item.id
    barrier = Barrier(2)

    def reclaim(_: int) -> list[str]:
        with database() as session:
            barrier.wait()
            return [item.lease_token or "" for item in claim_events(session, now=now, limit=1)]

    with ThreadPoolExecutor(max_workers=2) as executor:
        tokens = [token for batch in executor.map(reclaim, range(2)) for token in batch]
    assert len(tokens) == 1 and tokens[0] != "previous-token"
    with database() as session:
        assert not settle_success(session, event_id, "previous-token")
        assert not settle_failure(session, event_id, "previous-token")
        assert settle_success(session, event_id, tokens[0])
        session.commit()
    with database() as session:
        assert claim_events(session, now=now + timedelta(hours=1), limit=1) == []
        assert not settle_failure(session, event_id, tokens[0])


def test_completion_commit_failure_rolls_back_task_activity_and_event(
    database: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = Actor(uuid4(), "MANAGER")
    with database() as session:
        project_id = create_project(
            session, owner, key="PG-ROLLBACK", name="Rollback", description=None
        ).id
        task = create_task(
            session,
            owner,
            project_id,
            title="Rollback",
            description=None,
            priority=TaskPriority.MEDIUM,
            assignee_employee_id=None,
            due_date=None,
        )
        change_task_status(
            session, owner, project_id, task.id, status=TaskStatus.IN_PROGRESS, expected_version=1
        )
        task_id = task.id
    with database() as session:

        def fail_commit() -> None:
            raise RuntimeError("controlled pre-commit failure")

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="controlled pre-commit failure"):
            change_task_status(
                session, owner, project_id, task_id, status=TaskStatus.DONE, expected_version=2
            )
        session.rollback()
    with database() as session:
        task = session.get(Task, task_id)
        assert task and task.status == TaskStatus.IN_PROGRESS and task.version == 2
        assert (
            session.scalar(
                select(func.count())
                .select_from(WorkOutboxEvent)
                .where(WorkOutboxEvent.task_id == task_id)
            )
            == 0
        )
        activity_count = session.scalar(
            select(func.count()).select_from(TaskActivity).where(TaskActivity.task_id == task_id)
        )
        change_task_status(
            session, owner, project_id, task_id, status=TaskStatus.DONE, expected_version=2
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(TaskActivity)
                .where(TaskActivity.task_id == task_id)
            )
            == activity_count + 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(WorkOutboxEvent)
                .where(WorkOutboxEvent.task_id == task_id)
            )
            == 1
        )
