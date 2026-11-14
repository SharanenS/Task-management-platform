import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.event_publisher import claim_events, settle_failure, settle_success
from app.models import (
    Project,
    ProjectMembership,
    ProjectRole,
    ProjectStatus,
    Task,
    TaskActivity,
    TaskActivityType,
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
    change_member_role,
    change_task_status,
    create_project,
    create_task,
    get_dashboard_metrics,
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


def test_assignment_commit_failure_rolls_back_task_activity_and_event(
    database: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = Actor(uuid4(), "MANAGER")
    assignee = uuid4()
    with database() as session:
        project = create_project(
            session, owner, key="PG-ASSIGN-RB", name="Assign rollback", description=None
        )
        add_member(session, owner, project.id, assignee, ProjectRole.CONTRIBUTOR)
        task = create_task(
            session,
            owner,
            project.id,
            title="Assignment rollback",
            description=None,
            priority=TaskPriority.MEDIUM,
            assignee_employee_id=None,
            due_date=None,
        )
        project_id, task_id = project.id, task.id
    with database() as session:

        def fail_commit() -> None:
            raise RuntimeError("controlled assignment commit failure")

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="controlled assignment commit failure"):
            assign_task(
                session,
                owner,
                project_id,
                task_id,
                assignee_employee_id=assignee,
                expected_version=1,
            )
        session.rollback()
    with database() as session:
        task = session.get(Task, task_id)
        assert task and task.assignee_employee_id is None and task.version == 1
        assert (
            session.scalar(
                select(func.count())
                .select_from(WorkOutboxEvent)
                .where(
                    WorkOutboxEvent.task_id == task_id,
                    WorkOutboxEvent.event_type == "TASK_ASSIGNED",
                )
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(TaskActivity)
                .where(
                    TaskActivity.task_id == task_id,
                    TaskActivity.activity_type == TaskActivityType.ASSIGNMENT_CHANGED,
                )
            )
            == 0
        )


def test_postgres_dashboard_metrics_and_date_boundaries(
    database: sessionmaker[Session],
) -> None:
    owner = Actor(uuid4(), "MANAGER")
    member = Actor(uuid4(), "MEMBER")
    admin = Actor(uuid4(), "ADMIN")

    today = date.today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    with database() as session:
        # Project 1: Managed by owner, member is contributor. Status = ACTIVE
        p1 = Project(
            key="PGDASH1",
            name="Dashboard Proj 1",
            status=ProjectStatus.ACTIVE,
            creator_employee_id=owner.employee_id,
        )
        p1.memberships.append(
            ProjectMembership(employee_id=owner.employee_id, role=ProjectRole.PROJECT_MANAGER)
        )
        p1.memberships.append(
            ProjectMembership(employee_id=member.employee_id, role=ProjectRole.CONTRIBUTOR)
        )

        # Project 2: Owned by someone else, owner is contributor,
        # member is NOT member. Status = DRAFT
        p2 = Project(
            key="PGDASH2",
            name="Dashboard Proj 2",
            status=ProjectStatus.DRAFT,
            creator_employee_id=uuid4(),
        )
        p2.memberships.append(
            ProjectMembership(employee_id=owner.employee_id, role=ProjectRole.CONTRIBUTOR)
        )

        # Project 3: Unrelated project, member is contributor. Status = ARCHIVED
        p3 = Project(
            key="PGDASH3",
            name="Dashboard Proj 3",
            status=ProjectStatus.ARCHIVED,
            creator_employee_id=uuid4(),
        )
        p3.memberships.append(
            ProjectMembership(employee_id=member.employee_id, role=ProjectRole.CONTRIBUTOR)
        )

        session.add_all([p1, p2, p3])
        session.flush()

        # Tasks in Project 1 (managed by owner, member has access)
        t_yesterday_todo = Task(
            project_id=p1.id,
            number=1,
            title="Overdue Todo Task",
            status=TaskStatus.TODO,
            priority=TaskPriority.HIGH,
            assignee_employee_id=member.employee_id,
            creator_employee_id=owner.employee_id,
            due_date=yesterday,
        )
        t_today_todo = Task(
            project_id=p1.id,
            number=2,
            title="Due Today Task",
            status=TaskStatus.TODO,
            priority=TaskPriority.MEDIUM,
            assignee_employee_id=member.employee_id,
            creator_employee_id=owner.employee_id,
            due_date=today,
        )
        t_tomorrow_todo = Task(
            project_id=p1.id,
            number=3,
            title="Due Tomorrow Task",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.LOW,
            assignee_employee_id=owner.employee_id,
            creator_employee_id=owner.employee_id,
            due_date=tomorrow,
        )
        t_null_todo = Task(
            project_id=p1.id,
            number=4,
            title="No Due Date Task",
            status=TaskStatus.BLOCKED,
            priority=TaskPriority.MEDIUM,
            assignee_employee_id=owner.employee_id,
            creator_employee_id=owner.employee_id,
            due_date=None,
        )
        t_yesterday_done = Task(
            project_id=p1.id,
            number=5,
            title="Done Yesterday Task",
            status=TaskStatus.DONE,
            priority=TaskPriority.HIGH,
            assignee_employee_id=member.employee_id,
            creator_employee_id=owner.employee_id,
            due_date=yesterday,
        )
        t_yesterday_cancelled = Task(
            project_id=p1.id,
            number=6,
            title="Cancelled Yesterday Task",
            status=TaskStatus.CANCELLED,
            priority=TaskPriority.LOW,
            assignee_employee_id=member.employee_id,
            creator_employee_id=owner.employee_id,
            due_date=yesterday,
        )

        # Task in Project 2 (owner is contributor only, not manager)
        t_proj2 = Task(
            project_id=p2.id,
            number=1,
            title="Project 2 Task",
            status=TaskStatus.TODO,
            priority=TaskPriority.MEDIUM,
            assignee_employee_id=owner.employee_id,
            creator_employee_id=uuid4(),
            due_date=yesterday,
        )

        # Task in Project 3 (inaccessible to owner, member is contributor)
        t_proj3 = Task(
            project_id=p3.id,
            number=1,
            title="Project 3 Task",
            status=TaskStatus.TODO,
            priority=TaskPriority.MEDIUM,
            assignee_employee_id=member.employee_id,
            creator_employee_id=uuid4(),
            due_date=yesterday,
        )

        session.add_all(
            [
                t_yesterday_todo,
                t_today_todo,
                t_tomorrow_todo,
                t_null_todo,
                t_yesterday_done,
                t_yesterday_cancelled,
                t_proj2,
                t_proj3,
            ]
        )
        session.commit()

    with database() as session:
        # Check MEMBER dashboard
        m_dash = get_dashboard_metrics(session, member)
        assert m_dash.project_metrics.total_count == 2  # p1 (ACTIVE) and p3 (ARCHIVED)
        assert m_dash.project_metrics.active_count == 1
        assert m_dash.project_metrics.draft_count == 0
        assert m_dash.project_metrics.archived_count == 1
        assert m_dash.project_metrics.managed_total_count is None
        assert m_dash.task_metrics is None

        # Member personal assigned tasks: t_yesterday_todo, t_today_todo,
        # t_yesterday_done, t_yesterday_cancelled, t_proj3
        # Total assigned = 5
        assert m_dash.assigned_task_metrics.total_count == 5
        # Overdue assigned: t_yesterday_todo (p1) and t_proj3 (p3).
        # t_today_todo is due today (not overdue).
        # t_yesterday_done is DONE (not overdue).
        # t_yesterday_cancelled is CANCELLED (not overdue).
        assert m_dash.assigned_task_metrics.overdue_count == 2
        assert (
            m_dash.assigned_task_metrics.todo_count == 3
        )  # t_yesterday_todo, t_today_todo, t_proj3
        assert m_dash.assigned_task_metrics.done_count == 1
        assert m_dash.assigned_task_metrics.cancelled_count == 1

        # Check MANAGER dashboard
        mgr_dash = get_dashboard_metrics(session, owner)
        assert mgr_dash.project_metrics.total_count == 2  # p1 and p2 accessible
        assert mgr_dash.project_metrics.managed_total_count == 1  # p1 only
        assert mgr_dash.project_metrics.managed_active_count == 1

        # Manager task_metrics (scoped to managed project p1 only!)
        # Excludes t_proj2 (p2 is not managed) and t_proj3 (p3 is inaccessible)
        assert mgr_dash.task_metrics is not None
        assert mgr_dash.task_metrics.total_count == 6  # 6 tasks in p1
        assert mgr_dash.task_metrics.overdue_count == 1  # only t_yesterday_todo
        assert mgr_dash.task_metrics.todo_count == 2  # t_yesterday_todo, t_today_todo
        assert mgr_dash.task_metrics.in_progress_count == 1  # t_tomorrow_todo
        assert mgr_dash.task_metrics.blocked_count == 1  # t_null_todo
        assert mgr_dash.task_metrics.done_count == 1  # t_yesterday_done
        assert mgr_dash.task_metrics.cancelled_count == 1  # t_yesterday_cancelled

        # Manager assigned_task_metrics (personal assigned tasks across accessible
        # projects p1 and p2)
        # t_tomorrow_todo (p1), t_null_todo (p1), t_proj2 (p2) = 3 total
        assert mgr_dash.assigned_task_metrics.total_count == 3
        # Overdue assigned: t_proj2 (yesterday, TODO in accessible p2) = 1
        assert mgr_dash.assigned_task_metrics.overdue_count == 1

        # Check ADMIN dashboard
        adm_dash = get_dashboard_metrics(session, admin)
        assert adm_dash.project_metrics.total_count == 3
        assert adm_dash.project_metrics.managed_total_count == 3
        assert adm_dash.task_metrics is not None
        assert adm_dash.task_metrics.total_count == 8  # all 8 tasks across all projects
        # Overdue in entire system: t_yesterday_todo (p1), t_proj2 (p2), t_proj3 (p3) = 3
        assert adm_dash.task_metrics.overdue_count == 3


def test_postgres_dashboard_query_count_invariance(
    database: sessionmaker[Session],
) -> None:
    manager = Actor(uuid4(), "MANAGER")

    def seed_fixture(prefix: str, project_count: int, tasks_per_project: int) -> None:
        with database() as session:
            for i in range(project_count):
                p = Project(
                    key=f"{prefix}{i}",
                    name=f"Project {prefix} {i}",
                    status=ProjectStatus.ACTIVE if i % 2 == 0 else ProjectStatus.DRAFT,
                    creator_employee_id=manager.employee_id,
                )
                p.memberships.append(
                    ProjectMembership(
                        employee_id=manager.employee_id,
                        role=ProjectRole.PROJECT_MANAGER if i == 0 else ProjectRole.CONTRIBUTOR,
                    )
                )
                session.add(p)
                session.flush()

                for j in range(tasks_per_project):
                    t = Task(
                        project_id=p.id,
                        number=j + 1,
                        title=f"Task {j}",
                        status=TaskStatus.TODO if j % 2 == 0 else TaskStatus.DONE,
                        priority=TaskPriority.MEDIUM,
                        assignee_employee_id=manager.employee_id if j == 0 else None,
                        creator_employee_id=manager.employee_id,
                        due_date=date.today() - timedelta(days=1) if j == 0 else None,
                    )
                    session.add(t)
            session.commit()

    def count_queries() -> int:
        query_count = 0

        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            nonlocal query_count
            query_count += 1

        engine = database().get_bind()
        event.listen(engine, "before_cursor_execute", before_cursor_execute)
        try:
            with database() as session:
                dash = get_dashboard_metrics(session, manager)
                assert len(dash.recent_projects) <= 5
                assert len(dash.recent_assigned_tasks) <= 5
        finally:
            event.remove(engine, "before_cursor_execute", before_cursor_execute)
        return query_count

    # Small fixture: 2 projects, 3 tasks per project (6 tasks total)
    seed_fixture("SMPG", 2, 3)
    small_queries = count_queries()

    # Clear and populate large fixture: 8 projects, 10 tasks per project (80 tasks total)
    with database() as session:
        session.execute(delete(Task))
        session.execute(delete(ProjectMembership))
        session.execute(delete(Project))
        session.commit()

    seed_fixture("LRPG", 8, 10)
    large_queries = count_queries()

    # Exact statement count invariance: query count MUST NOT grow with scale (O(1))
    assert small_queries == large_queries
    assert small_queries == 6  # Exactly 6 SQL statements


def test_postgres_revocation_isolation_and_manager_authority_reduction(
    database: sessionmaker[Session],
) -> None:
    member = Actor(uuid4(), "MEMBER")
    manager = Actor(uuid4(), "MANAGER")
    other_mgr = Actor(uuid4(), "MANAGER")

    with database() as session:
        # Project 1: ACTIVE. manager is PROJECT_MANAGER,
        # other_mgr is PROJECT_MANAGER, member is CONTRIBUTOR.
        p1 = Project(
            key="PGREV1",
            name="PG Revocation Proj 1",
            status=ProjectStatus.ACTIVE,
            creator_employee_id=manager.employee_id,
        )
        p1.memberships.append(
            ProjectMembership(employee_id=manager.employee_id, role=ProjectRole.PROJECT_MANAGER)
        )
        p1.memberships.append(
            ProjectMembership(employee_id=other_mgr.employee_id, role=ProjectRole.PROJECT_MANAGER)
        )
        p1.memberships.append(
            ProjectMembership(employee_id=member.employee_id, role=ProjectRole.CONTRIBUTOR)
        )

        # Project 2: ACTIVE. other_mgr is PROJECT_MANAGER,
        # manager is CONTRIBUTOR, member is CONTRIBUTOR.
        p2 = Project(
            key="PGREV2",
            name="PG Revocation Proj 2",
            status=ProjectStatus.ACTIVE,
            creator_employee_id=other_mgr.employee_id,
        )
        p2.memberships.append(
            ProjectMembership(employee_id=other_mgr.employee_id, role=ProjectRole.PROJECT_MANAGER)
        )
        p2.memberships.append(
            ProjectMembership(employee_id=manager.employee_id, role=ProjectRole.CONTRIBUTOR)
        )
        p2.memberships.append(
            ProjectMembership(employee_id=member.employee_id, role=ProjectRole.CONTRIBUTOR)
        )

        session.add_all([p1, p2])
        session.flush()

        # Task 1 assigned to member in P1 (overdue)
        t1 = Task(
            project_id=p1.id,
            number=1,
            title="Member Task in PG P1",
            status=TaskStatus.TODO,
            priority=TaskPriority.HIGH,
            assignee_employee_id=member.employee_id,
            creator_employee_id=manager.employee_id,
            due_date=date.today() - timedelta(days=1),
        )
        # Task 2 assigned to manager in P1
        t2 = Task(
            project_id=p1.id,
            number=2,
            title="Manager Task in PG P1",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.MEDIUM,
            assignee_employee_id=manager.employee_id,
            creator_employee_id=manager.employee_id,
        )
        # Task 3 assigned to member in P2
        t3 = Task(
            project_id=p2.id,
            number=1,
            title="Member Task in PG P2",
            status=TaskStatus.TODO,
            priority=TaskPriority.LOW,
            assignee_employee_id=member.employee_id,
            creator_employee_id=other_mgr.employee_id,
        )

        session.add_all([t1, t2, t3])
        session.commit()

    with database() as session:
        # 1. Baseline verification
        mem_dash = get_dashboard_metrics(session, member)
        assert mem_dash.project_metrics.total_count == 2
        assert mem_dash.assigned_task_metrics.total_count == 2
        assert mem_dash.assigned_task_metrics.overdue_count == 1
        assert len(mem_dash.recent_assigned_tasks) == 2

        mgr_dash = get_dashboard_metrics(session, manager)
        assert mgr_dash.project_metrics.total_count == 2
        assert mgr_dash.project_metrics.managed_total_count == 1
        assert mgr_dash.task_metrics is not None
        assert mgr_dash.task_metrics.total_count == 2
        assert mgr_dash.assigned_task_metrics.total_count == 1

        # 2. Document and test normal membership removal behavior
        # Normal removal via remove_member must fail closed with MEMBER_HAS_ASSIGNED_TASKS
        with pytest.raises(WorkError) as exc_info:
            remove_member(session, manager, p1.id, member.employee_id)
        assert exc_info.value.code == "MEMBER_HAS_ASSIGNED_TASKS"

        # 3. Test aggregate's defense against stale assignment without adding a product backdoor:
        # Directly delete member's ProjectMembership from p1, leaving t1 still assigned
        mem_record = session.scalar(
            select(ProjectMembership).where(
                ProjectMembership.project_id == p1.id,
                ProjectMembership.employee_id == member.employee_id,
            )
        )
        assert mem_record is not None
        session.delete(mem_record)
        session.commit()

        # Verify fixture genuinely retains the assignment after membership removal
        refreshed_t1 = session.scalar(select(Task).where(Task.id == t1.id))
        assert refreshed_t1 is not None
        assert refreshed_t1.assignee_employee_id == member.employee_id

        # Prove the next dashboard aggregate excludes that task and project
        mem_dash_after = get_dashboard_metrics(session, member)
        assert mem_dash_after.project_metrics.total_count == 1  # p1 excluded, only p2 remains
        assert mem_dash_after.assigned_task_metrics.total_count == 1  # t1 excluded, only t3 in p2
        assert (
            mem_dash_after.assigned_task_metrics.overdue_count == 0
        )  # t1 was overdue, now excluded
        assert len(mem_dash_after.recent_assigned_tasks) == 1
        assert mem_dash_after.recent_assigned_tasks[0].id == t3.id

        # 4. Manager authority reduction:
        # Reduce manager's authority in p1 from PROJECT_MANAGER to CONTRIBUTOR
        change_member_role(session, other_mgr, p1.id, manager.employee_id, ProjectRole.CONTRIBUTOR)

        # Prove manager loses managed totals while preserving
        # accessible-project and personal-work scopes
        mgr_dash_after = get_dashboard_metrics(session, manager)
        assert (
            mgr_dash_after.project_metrics.total_count == 2
        )  # still accessible (contributor in p1 & p2)
        assert mgr_dash_after.project_metrics.managed_total_count == 0  # lost managed total
        assert mgr_dash_after.project_metrics.managed_active_count == 0
        assert mgr_dash_after.task_metrics is not None
        assert mgr_dash_after.task_metrics.total_count == 0  # no managed tasks
        assert mgr_dash_after.assigned_task_metrics.total_count == 1  # t2 personal task preserved
        assert len(mgr_dash_after.recent_assigned_tasks) == 1
        assert mgr_dash_after.recent_assigned_tasks[0].id == t2.id
