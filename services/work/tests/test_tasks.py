from datetime import date
from itertools import product
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import (
    ProjectMembership,
    ProjectRole,
    ProjectStatus,
    Task,
    TaskActivity,
    TaskActivityType,
    TaskPriority,
    TaskStatus,
)
from app.schemas import TaskCommentCreateRequest, TaskCreateRequest, TaskUpdateRequest
from app.service import (
    Actor,
    WorkError,
    add_member,
    add_task_comment,
    assign_task,
    change_task_status,
    create_project,
    create_task,
    get_task,
    list_task_activity,
    list_task_comments,
    list_tasks,
    remove_member,
    set_status,
    task_board,
    update_task,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as value:
        yield value


def setup_project(session: Session, *, key: str = "TASKS") -> tuple[Actor, object]:
    manager = Actor(uuid4(), "MANAGER")
    project = create_project(session, manager, key=key, name="Tasks", description=None)
    return manager, project


def new_task(session: Session, actor: Actor, project_id: object, **values: object):
    return create_task(
        session,
        actor,
        project_id,  # type: ignore[arg-type]
        title=str(values.get("title", "First task")),
        description=values.get("description"),  # type: ignore[arg-type]
        priority=values.get("priority", TaskPriority.MEDIUM),  # type: ignore[arg-type]
        assignee_employee_id=values.get("assignee_employee_id"),  # type: ignore[arg-type]
        due_date=values.get("due_date"),  # type: ignore[arg-type]
    )


def test_task_schema_normalizes_and_validates() -> None:
    value = TaskCreateRequest(title="  Review   changes ", priority="HIGH")
    assert value.title == "Review changes"
    assert value.priority == TaskPriority.HIGH
    with pytest.raises(ValidationError):
        TaskCreateRequest(title="   ")
    with pytest.raises(ValidationError):
        TaskCommentCreateRequest(body="   ")


def test_manager_contributor_and_admin_create_tasks_with_atomic_activity(session: Session) -> None:
    manager, project = setup_project(session)
    contributor = Actor(uuid4(), "MEMBER")
    add_member(session, manager, project.id, contributor.employee_id, ProjectRole.CONTRIBUTOR)
    first = new_task(session, manager, project.id)
    second = new_task(session, contributor, project.id, title="Contributor task")
    third = new_task(session, Actor(uuid4(), "ADMIN"), project.id, title="Admin task")
    assert [first.number, second.number, third.number] == [1, 2, 3]
    assert second.creator_employee_id == contributor.employee_id
    activities = session.scalars(select(TaskActivity).order_by(TaskActivity.task_id)).all()
    assert len(activities) == 3
    assert {item.activity_type for item in activities} == {TaskActivityType.CREATED}
    for operation in (
        lambda: update_task(
            session,
            contributor,
            project.id,
            second.id,
            title="Not allowed",
            description=None,
            priority=TaskPriority.HIGH,
            due_date=None,
            expected_version=1,
        ),
        lambda: assign_task(
            session,
            contributor,
            project.id,
            second.id,
            assignee_employee_id=contributor.employee_id,
            expected_version=1,
        ),
    ):
        with pytest.raises(WorkError) as denied:
            operation()
        assert denied.value.code == "FORBIDDEN"


def test_non_member_cannot_create_or_infer_task(session: Session) -> None:
    manager, project = setup_project(session)
    task = new_task(session, manager, project.id)
    outsider = Actor(uuid4(), "MANAGER")
    for operation in (
        lambda: new_task(session, outsider, project.id),
        lambda: get_task(session, outsider, project.id, task.id),
        lambda: list_tasks(
            session,
            outsider,
            project.id,
            first=20,
            after=None,
            search=None,
            status=None,
            priority=None,
            assignee_employee_id=None,
            unassigned=False,
        ),
    ):
        with pytest.raises(WorkError) as caught:
            operation()
        assert caught.value.code == "FORBIDDEN"


def test_archived_project_rejects_every_task_mutation(session: Session) -> None:
    manager, project = setup_project(session)
    task = new_task(session, manager, project.id)
    project = set_status(
        session, manager, project.id, status=ProjectStatus.ACTIVE, expected_version=1
    )
    set_status(session, manager, project.id, status=ProjectStatus.ARCHIVED, expected_version=2)
    operations = (
        lambda: new_task(session, manager, project.id),
        lambda: update_task(
            session,
            manager,
            project.id,
            task.id,
            title="Changed",
            description=None,
            priority=TaskPriority.LOW,
            due_date=None,
            expected_version=1,
        ),
        lambda: assign_task(
            session,
            manager,
            project.id,
            task.id,
            assignee_employee_id=None,
            expected_version=1,
        ),
        lambda: change_task_status(
            session,
            manager,
            project.id,
            task.id,
            status=TaskStatus.IN_PROGRESS,
            expected_version=1,
        ),
        lambda: add_task_comment(session, manager, project.id, task.id, body="No"),
    )
    activity_count = session.scalar(select(func.count()).select_from(TaskActivity))
    for operation in operations:
        with pytest.raises(WorkError) as caught:
            operation()
        assert caught.value.code == "PROJECT_ARCHIVED"
        session.rollback()
        assert session.scalar(select(func.count()).select_from(TaskActivity)) == activity_count
    assert get_task(session, manager, project.id, task.id).id == task.id


def test_exhaustive_status_transition_matrix_is_atomic(session: Session) -> None:
    allowed = {
        (TaskStatus.TODO, TaskStatus.IN_PROGRESS),
        (TaskStatus.TODO, TaskStatus.BLOCKED),
        (TaskStatus.TODO, TaskStatus.CANCELLED),
        (TaskStatus.IN_PROGRESS, TaskStatus.TODO),
        (TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED),
        (TaskStatus.IN_PROGRESS, TaskStatus.DONE),
        (TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED),
        (TaskStatus.BLOCKED, TaskStatus.TODO),
        (TaskStatus.BLOCKED, TaskStatus.IN_PROGRESS),
        (TaskStatus.BLOCKED, TaskStatus.CANCELLED),
        (TaskStatus.DONE, TaskStatus.IN_PROGRESS),
        (TaskStatus.CANCELLED, TaskStatus.TODO),
    }
    for start, target in product(TaskStatus, repeat=2):
        manager, project = setup_project(
            session, key=f"S-{start.value[:2]}-{target.value[:2]}-{uuid4().hex[:6]}"
        )
        task = new_task(session, manager, project.id, title=f"{start}-{target}")
        task.status = start
        session.commit()
        before_count = session.scalar(select(func.count()).select_from(TaskActivity))
        before_version = task.version
        if start == target:
            unchanged = change_task_status(
                session, manager, project.id, task.id, status=target, expected_version=1
            )
            assert (unchanged.status, unchanged.version) == (start, before_version)
            assert session.scalar(select(func.count()).select_from(TaskActivity)) == before_count
        elif (start, target) in allowed:
            changed = change_task_status(
                session, manager, project.id, task.id, status=target, expected_version=1
            )
            assert (changed.status, changed.version) == (target, before_version + 1)
            latest = session.scalar(
                select(TaskActivity).where(
                    TaskActivity.task_id == task.id,
                    TaskActivity.activity_type == TaskActivityType.STATUS_CHANGED,
                )
            )
            assert latest is not None
            assert latest.change_data == {
                "from": start.value,
                "to": target.value,
                "version": before_version + 1,
            }
        else:
            with pytest.raises(WorkError) as caught:
                change_task_status(
                    session, manager, project.id, task.id, status=target, expected_version=1
                )
            assert caught.value.code == "INVALID_TASK_STATUS"
            session.expire_all()
            unchanged = session.get(Task, task.id)
            assert unchanged is not None
            assert (unchanged.status, unchanged.version) == (start, before_version)
            assert session.scalar(select(func.count()).select_from(TaskActivity)) == before_count


def test_contributor_changes_only_assigned_task_status(session: Session) -> None:
    manager, project = setup_project(session)
    contributor = Actor(uuid4(), "MEMBER")
    other = uuid4()
    add_member(session, manager, project.id, contributor.employee_id, ProjectRole.CONTRIBUTOR)
    add_member(session, manager, project.id, other, ProjectRole.CONTRIBUTOR)
    assigned = new_task(session, manager, project.id, assignee_employee_id=contributor.employee_id)
    changed = change_task_status(
        session,
        contributor,
        project.id,
        assigned.id,
        status=TaskStatus.IN_PROGRESS,
        expected_version=1,
    )
    assert changed.status == TaskStatus.IN_PROGRESS
    other_task = new_task(session, manager, project.id, assignee_employee_id=other)
    with pytest.raises(WorkError) as caught:
        change_task_status(
            session,
            contributor,
            project.id,
            other_task.id,
            status=TaskStatus.IN_PROGRESS,
            expected_version=1,
        )
    assert caught.value.code == "FORBIDDEN"


def test_assignment_requires_manager_current_membership_and_version(session: Session) -> None:
    manager, project = setup_project(session)
    contributor = uuid4()
    task = new_task(session, manager, project.id)
    with pytest.raises(WorkError) as invalid:
        assign_task(
            session,
            manager,
            project.id,
            task.id,
            assignee_employee_id=contributor,
            expected_version=1,
        )
    assert invalid.value.code == "INVALID_ASSIGNEE"
    add_member(session, manager, project.id, contributor, ProjectRole.CONTRIBUTOR)
    task = assign_task(
        session,
        manager,
        project.id,
        task.id,
        assignee_employee_id=contributor,
        expected_version=1,
    )
    assert task.assignee_employee_id == contributor
    assignment_activity = session.scalars(
        select(TaskActivity).where(TaskActivity.task_id == task.id)
    ).all()
    assert {item.activity_type for item in assignment_activity} == {
        TaskActivityType.CREATED,
        TaskActivityType.ASSIGNMENT_CHANGED,
    }
    assignment_event = next(
        item
        for item in assignment_activity
        if item.activity_type == TaskActivityType.ASSIGNMENT_CHANGED
    )
    assert set(assignment_event.change_data) == {
        "from_employee_id",
        "to_employee_id",
        "version",
    }
    with pytest.raises(WorkError) as stale:
        assign_task(
            session,
            manager,
            project.id,
            task.id,
            assignee_employee_id=None,
            expected_version=1,
        )
    assert stale.value.code == "VERSION_CONFLICT"


def test_assigned_member_removal_is_blocked_until_unassigned(session: Session) -> None:
    manager, project = setup_project(session)
    contributor = uuid4()
    add_member(session, manager, project.id, contributor, ProjectRole.CONTRIBUTOR)
    task = new_task(session, manager, project.id, assignee_employee_id=contributor)

    with pytest.raises(WorkError) as blocked:
        remove_member(session, manager, project.id, contributor)
    assert blocked.value.code == "MEMBER_HAS_ASSIGNED_TASKS"
    assert blocked.value.message == (
        "Reassign the employee's tasks before removing project membership."
    )
    assert (
        session.scalar(
            select(ProjectMembership).where(
                ProjectMembership.project_id == project.id,
                ProjectMembership.employee_id == contributor,
            )
        )
        is not None
    )
    assert session.get(Task, task.id).assignee_employee_id == contributor

    task = assign_task(
        session,
        manager,
        project.id,
        task.id,
        assignee_employee_id=None,
        expected_version=1,
    )
    result = remove_member(session, manager, project.id, contributor)
    assert contributor not in {item.employee_id for item in result.memberships}
    assert session.get(Task, task.id).assignee_employee_id is None


def test_final_manager_protection_precedes_assigned_task_guard(session: Session) -> None:
    manager, project = setup_project(session)
    new_task(session, manager, project.id, assignee_employee_id=manager.employee_id)
    with pytest.raises(WorkError) as blocked:
        remove_member(session, manager, project.id, manager.employee_id)
    assert blocked.value.code == "FINAL_PROJECT_MANAGER"


def test_manager_updates_metadata_and_contributor_is_denied(session: Session) -> None:
    manager, project = setup_project(session)
    contributor = Actor(uuid4(), "MEMBER")
    add_member(session, manager, project.id, contributor.employee_id, ProjectRole.CONTRIBUTOR)
    task = new_task(session, manager, project.id)
    with pytest.raises(WorkError) as denied:
        update_task(
            session,
            contributor,
            project.id,
            task.id,
            title="Denied",
            description=None,
            priority=TaskPriority.HIGH,
            due_date=None,
            expected_version=1,
        )
    assert denied.value.code == "FORBIDDEN"
    changed = update_task(
        session,
        manager,
        project.id,
        task.id,
        title="Updated",
        description="Text",
        priority=TaskPriority.URGENT,
        due_date=date(2026, 12, 1),
        expected_version=1,
    )
    assert (changed.title, changed.priority, changed.version) == (
        "Updated",
        TaskPriority.URGENT,
        2,
    )
    metadata_activity = session.scalars(
        select(TaskActivity).where(TaskActivity.task_id == changed.id)
    ).all()
    assert {item.activity_type for item in metadata_activity} == {
        TaskActivityType.CREATED,
        TaskActivityType.METADATA_UPDATED,
    }
    metadata_event = next(
        item
        for item in metadata_activity
        if item.activity_type == TaskActivityType.METADATA_UPDATED
    )
    assert metadata_event.change_data == {"version": 2}


def test_due_date_contract_create_update_clear_invalid_and_stale(session: Session) -> None:
    manager, project = setup_project(session)
    without_due_date = new_task(session, manager, project.id, title="No date")
    with_due_date = new_task(session, manager, project.id, title="Date", due_date=date(2026, 12, 1))
    assert without_due_date.due_date is None
    assert with_due_date.due_date == date(2026, 12, 1)

    updated = update_task(
        session,
        manager,
        project.id,
        without_due_date.id,
        title="No date",
        description=None,
        priority=TaskPriority.MEDIUM,
        due_date=date(2027, 1, 2),
        expected_version=1,
    )
    assert updated.due_date == date(2027, 1, 2)
    cleared = update_task(
        session,
        manager,
        project.id,
        updated.id,
        title="No date",
        description=None,
        priority=TaskPriority.MEDIUM,
        due_date=None,
        expected_version=2,
    )
    assert cleared.due_date is None
    before_activity = session.scalar(select(func.count()).select_from(TaskActivity))
    with pytest.raises(WorkError) as stale:
        update_task(
            session,
            manager,
            project.id,
            cleared.id,
            title="Stale",
            description=None,
            priority=TaskPriority.MEDIUM,
            due_date=date(2030, 1, 1),
            expected_version=1,
        )
    assert stale.value.code == "VERSION_CONFLICT"
    session.expire_all()
    unchanged = session.get(Task, cleared.id)
    assert unchanged is not None
    assert (unchanged.due_date, unchanged.version) == (None, 3)
    assert session.scalar(select(func.count()).select_from(TaskActivity)) == before_activity

    parsed = TaskCreateRequest(title="Date", due_date="2026-12-01")
    assert parsed.due_date == date(2026, 12, 1)
    assert parsed.model_dump(mode="json")["due_date"] == "2026-12-01"
    with pytest.raises(ValidationError):
        TaskCreateRequest(title="Date", due_date="2026-02-30")
    with pytest.raises(ValidationError):
        TaskUpdateRequest(
            title="Date",
            priority=TaskPriority.MEDIUM,
            due_date="2026-12-01T23:00:00-05:00",
            expected_version=1,
        )


def test_failed_mutations_leave_no_activity_and_success_data_is_allowlisted(
    session: Session,
) -> None:
    manager, project = setup_project(session)
    target = uuid4()
    task = new_task(session, manager, project.id)
    baseline = session.scalar(select(func.count()).select_from(TaskActivity))

    with pytest.raises(WorkError) as assignment:
        assign_task(
            session,
            manager,
            project.id,
            task.id,
            assignee_employee_id=target,
            expected_version=1,
        )
    assert assignment.value.code == "INVALID_ASSIGNEE"
    assert session.scalar(select(func.count()).select_from(TaskActivity)) == baseline

    for invalid_body in ("   ", "x" * 4001):
        with pytest.raises(WorkError) as comment:
            add_task_comment(session, manager, project.id, task.id, body=invalid_body)
        assert comment.value.code == "INVALID_COMMENT"
        assert session.scalar(select(func.count()).select_from(TaskActivity)) == baseline

    created = add_task_comment(
        session, manager, project.id, task.id, body="  plain sensitive-looking text  "
    )
    assert created.body == "plain sensitive-looking text"
    activity = session.scalar(
        select(TaskActivity).where(
            TaskActivity.task_id == task.id,
            TaskActivity.activity_type == TaskActivityType.COMMENT_ADDED,
        )
    )
    assert activity is not None
    assert set(activity.change_data) == {"comment_id"}
    assert "plain sensitive-looking text" not in str(activity.change_data)


def test_filters_pagination_board_and_bad_cursor(session: Session) -> None:
    manager, project = setup_project(session)
    first = new_task(session, manager, project.id, title="Alpha", priority=TaskPriority.HIGH)
    second = new_task(session, manager, project.id, title="Beta", priority=TaskPriority.LOW)
    second.status = TaskStatus.BLOCKED
    session.commit()
    page = list_tasks(
        session,
        manager,
        project.id,
        first=1,
        after=None,
        search=None,
        status=None,
        priority=None,
        assignee_employee_id=None,
        unassigned=True,
    )
    assert page.has_next_page and page.next_cursor
    assert len(page.items) == 1
    filtered = list_tasks(
        session,
        manager,
        project.id,
        first=20,
        after=None,
        search="beta",
        status=TaskStatus.BLOCKED,
        priority=TaskPriority.LOW,
        assignee_employee_id=None,
        unassigned=False,
    )
    assert [item.id for item in filtered.items] == [second.id]
    lanes = task_board(session, manager, project.id, lane_size=1)
    assert lanes[TaskStatus.TODO][0][0].id == first.id
    with pytest.raises(WorkError) as cursor:
        list_tasks(
            session,
            manager,
            project.id,
            first=20,
            after="bad",
            search=None,
            status=None,
            priority=None,
            assignee_employee_id=None,
            unassigned=False,
        )
    assert cursor.value.code == "INVALID_CURSOR"


def test_comments_and_activity_are_ordered_paginated_and_non_sensitive(session: Session) -> None:
    manager, project = setup_project(session)
    task = new_task(session, manager, project.id)
    first = add_task_comment(session, manager, project.id, task.id, body="First")
    second = add_task_comment(session, manager, project.id, task.id, body="Second")
    page = list_task_comments(session, manager, project.id, task.id, first=1, after=None)
    assert page.has_next_page and page.items[0].id in {first.id, second.id}
    activity = list_task_activity(session, manager, project.id, task.id, first=20, after=None)
    assert [item.activity_type for item in activity.items].count(
        TaskActivityType.COMMENT_ADDED
    ) == 2
    assert all("First" not in str(item.change_data) for item in activity.items)


def test_task_comment_and_activity_cursor_boundaries_are_stable(session: Session) -> None:
    manager, project = setup_project(session)
    tasks = [new_task(session, manager, project.id, title=f"Task {index}") for index in range(3)]
    # UUID ordering is the stable tie-breaker even when timestamps are identical.
    shared_time = tasks[0].created_at
    for task in tasks:
        task.created_at = shared_time
    session.commit()
    first_tasks = list_tasks(
        session,
        manager,
        project.id,
        first=2,
        after=None,
        search=None,
        status=None,
        priority=None,
        assignee_employee_id=None,
        unassigned=False,
    )
    second_tasks = list_tasks(
        session,
        manager,
        project.id,
        first=2,
        after=first_tasks.next_cursor,
        search=None,
        status=None,
        priority=None,
        assignee_employee_id=None,
        unassigned=False,
    )
    task_ids = [item.id for item in first_tasks.items + second_tasks.items]
    assert task_ids == sorted(task_ids)
    assert len(task_ids) == len(set(task_ids)) == 3

    task = tasks[0]
    comments = [
        add_task_comment(session, manager, project.id, task.id, body=f"Comment {index}")
        for index in range(3)
    ]
    for comment in comments:
        comment.created_at = comments[0].created_at
    session.commit()
    comment_page_one = list_task_comments(
        session, manager, project.id, task.id, first=2, after=None
    )
    comment_page_two = list_task_comments(
        session,
        manager,
        project.id,
        task.id,
        first=2,
        after=comment_page_one.next_cursor,
    )
    comment_ids = [item.id for item in comment_page_one.items + comment_page_two.items]
    assert comment_ids == sorted(comment_ids)
    assert len(comment_ids) == len(set(comment_ids)) == 3

    activity_page_one = list_task_activity(
        session, manager, project.id, task.id, first=2, after=None
    )
    activity_page_two = list_task_activity(
        session,
        manager,
        project.id,
        task.id,
        first=20,
        after=activity_page_one.next_cursor,
    )
    activity_ids = [item.id for item in activity_page_one.items + activity_page_two.items]
    assert activity_ids == sorted(activity_ids)
    assert len(activity_ids) == len(set(activity_ids))

    calls = (
        lambda size, cursor: list_tasks(
            session,
            manager,
            project.id,
            first=size,
            after=cursor,
            search=None,
            status=None,
            priority=None,
            assignee_employee_id=None,
            unassigned=False,
        ),
        lambda size, cursor: list_task_comments(
            session, manager, project.id, task.id, first=size, after=cursor
        ),
        lambda size, cursor: list_task_activity(
            session, manager, project.id, task.id, first=size, after=cursor
        ),
    )
    for call in calls:
        for invalid_size in (0, 51):
            with pytest.raises(WorkError) as size_error:
                call(invalid_size, None)
            assert size_error.value.code == "INVALID_PAGE_SIZE"
        with pytest.raises(WorkError) as cursor_error:
            call(20, "malformed")
        assert cursor_error.value.code == "INVALID_CURSOR"
