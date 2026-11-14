from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_session
from app.main import app
from app.models import (
    Project,
    ProjectMembership,
    ProjectRole,
    ProjectStatus,
    Task,
    TaskPriority,
    TaskStatus,
)
from app.service import (
    Actor,
    WorkError,
    change_member_role,
    get_dashboard_metrics,
    remove_member,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as s:
        yield s


def make_actor(role: str = "MEMBER") -> Actor:
    return Actor(uuid4(), role)


def test_empty_workspace_returns_zeros(session: Session) -> None:
    member = make_actor("MEMBER")
    data = get_dashboard_metrics(session, member)
    assert data.project_metrics.total_count == 0
    assert data.project_metrics.active_count == 0
    assert data.project_metrics.draft_count == 0
    assert data.project_metrics.archived_count == 0
    assert data.project_metrics.managed_total_count is None
    assert data.task_metrics is None
    assert data.assigned_task_metrics.total_count == 0
    assert data.assigned_task_metrics.overdue_count == 0
    assert len(data.recent_projects) == 0
    assert len(data.recent_assigned_tasks) == 0


def test_member_metrics_and_scoping(session: Session) -> None:
    member = make_actor("MEMBER")
    other_user = make_actor("MEMBER")

    # Accessible project 1: ACTIVE
    p1 = Project(
        key="ACC1",
        name="Accessible 1",
        status=ProjectStatus.ACTIVE,
        creator_employee_id=member.employee_id,
    )
    p1.memberships.append(
        ProjectMembership(employee_id=member.employee_id, role=ProjectRole.CONTRIBUTOR)
    )
    # Accessible project 2: ARCHIVED
    p2 = Project(
        key="ACC2",
        name="Accessible 2",
        status=ProjectStatus.ARCHIVED,
        creator_employee_id=member.employee_id,
    )
    p2.memberships.append(
        ProjectMembership(employee_id=member.employee_id, role=ProjectRole.CONTRIBUTOR)
    )
    # Inaccessible project: ACTIVE
    p3 = Project(
        key="INACC",
        name="Inaccessible",
        status=ProjectStatus.ACTIVE,
        creator_employee_id=other_user.employee_id,
    )
    p3.memberships.append(
        ProjectMembership(employee_id=other_user.employee_id, role=ProjectRole.CONTRIBUTOR)
    )

    session.add_all([p1, p2, p3])
    session.flush()

    today = date.today()
    # Task assigned to member in p1 (overdue)
    t1 = Task(
        project_id=p1.id,
        number=1,
        title="T1",
        status=TaskStatus.TODO,
        priority=TaskPriority.HIGH,
        assignee_employee_id=member.employee_id,
        creator_employee_id=member.employee_id,
        due_date=today - timedelta(days=1),
    )
    # Task assigned to member in p1 (due today - not overdue)
    t2 = Task(
        project_id=p1.id,
        number=2,
        title="T2",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.MEDIUM,
        assignee_employee_id=member.employee_id,
        creator_employee_id=member.employee_id,
        due_date=today,
    )
    # Task assigned to member in p2 (archived project, DONE, past due date - not overdue)
    t3 = Task(
        project_id=p2.id,
        number=1,
        title="T3",
        status=TaskStatus.DONE,
        priority=TaskPriority.LOW,
        assignee_employee_id=member.employee_id,
        creator_employee_id=member.employee_id,
        due_date=today - timedelta(days=5),
    )
    # Task assigned to other user in p1
    t4 = Task(
        project_id=p1.id,
        number=3,
        title="T4",
        status=TaskStatus.TODO,
        priority=TaskPriority.LOW,
        assignee_employee_id=other_user.employee_id,
        creator_employee_id=other_user.employee_id,
    )
    # Task assigned to member in inaccessible project p3 (must not count for member!)
    t5 = Task(
        project_id=p3.id,
        number=1,
        title="T5",
        status=TaskStatus.TODO,
        priority=TaskPriority.HIGH,
        assignee_employee_id=member.employee_id,
        creator_employee_id=other_user.employee_id,
        due_date=today - timedelta(days=2),
    )

    session.add_all([t1, t2, t3, t4, t5])
    session.commit()

    data = get_dashboard_metrics(session, member)

    # Project metrics: p1 (ACTIVE) + p2 (ARCHIVED) = 2 total, 1 active, 0 draft, 1 archived.
    # p3 is excluded because member is not assigned to it.
    assert data.project_metrics.total_count == 2
    assert data.project_metrics.active_count == 1
    assert data.project_metrics.draft_count == 0
    assert data.project_metrics.archived_count == 1
    assert data.project_metrics.managed_total_count is None

    # Member task metrics is None (members only have assigned task metrics)
    assert data.task_metrics is None

    # Assigned task metrics: t1, t2, t3 (t4 not assigned to member; t5 in inaccessible project p3)
    assert data.assigned_task_metrics.total_count == 3
    assert data.assigned_task_metrics.todo_count == 1  # t1
    assert data.assigned_task_metrics.in_progress_count == 1  # t2
    assert data.assigned_task_metrics.done_count == 1  # t3
    assert (
        data.assigned_task_metrics.overdue_count == 1
    )  # only t1 is overdue (t2 is due today, t3 is DONE)

    # Recent previews
    assert len(data.recent_projects) == 2
    assert {p.key for p in data.recent_projects} == {"ACC1", "ACC2"}
    assert len(data.recent_assigned_tasks) == 3


def test_manager_metrics_distinguishes_managed_and_accessible(session: Session) -> None:
    manager = make_actor("MANAGER")
    other = make_actor("MANAGER")

    # Project managed by manager
    p_managed = Project(
        key="MGD",
        name="Managed",
        status=ProjectStatus.ACTIVE,
        creator_employee_id=manager.employee_id,
    )
    p_managed.memberships.append(
        ProjectMembership(employee_id=manager.employee_id, role=ProjectRole.PROJECT_MANAGER)
    )

    # Project where manager is only a contributor
    p_contrib = Project(
        key="CTB",
        name="Contributor",
        status=ProjectStatus.DRAFT,
        creator_employee_id=other.employee_id,
    )
    p_contrib.memberships.append(
        ProjectMembership(employee_id=other.employee_id, role=ProjectRole.PROJECT_MANAGER)
    )
    p_contrib.memberships.append(
        ProjectMembership(employee_id=manager.employee_id, role=ProjectRole.CONTRIBUTOR)
    )

    # Inaccessible project
    p_inacc = Project(
        key="OTH", name="Other", status=ProjectStatus.ACTIVE, creator_employee_id=other.employee_id
    )
    p_inacc.memberships.append(
        ProjectMembership(employee_id=other.employee_id, role=ProjectRole.PROJECT_MANAGER)
    )

    session.add_all([p_managed, p_contrib, p_inacc])
    session.flush()

    # Tasks in managed project
    t1 = Task(
        project_id=p_managed.id,
        number=1,
        title="T1",
        status=TaskStatus.TODO,
        priority=TaskPriority.HIGH,
        creator_employee_id=manager.employee_id,
    )
    t2 = Task(
        project_id=p_managed.id,
        number=2,
        title="T2",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.LOW,
        creator_employee_id=manager.employee_id,
    )
    # Task in contributor project
    t3 = Task(
        project_id=p_contrib.id,
        number=1,
        title="T3",
        status=TaskStatus.BLOCKED,
        priority=TaskPriority.MEDIUM,
        creator_employee_id=other.employee_id,
    )

    session.add_all([t1, t2, t3])
    session.commit()

    data = get_dashboard_metrics(session, manager)

    # Accessible projects: 2 (MGD + CTB)
    assert data.project_metrics.total_count == 2
    assert data.project_metrics.active_count == 1
    assert data.project_metrics.draft_count == 1
    # Managed projects: 1 (only MGD)
    assert data.project_metrics.managed_total_count == 1
    assert data.project_metrics.managed_active_count == 1
    assert data.project_metrics.managed_draft_count == 0

    # Task metrics for manager: only tasks in MANAGED projects (t1 and t2)
    assert data.task_metrics is not None
    assert data.task_metrics.total_count == 2
    assert data.task_metrics.todo_count == 1
    assert data.task_metrics.in_progress_count == 1
    assert data.task_metrics.blocked_count == 0  # t3 in p_contrib is NOT counted in managed tasks!


def test_revocation_isolation_stale_assignment_and_manager_authority_reduction(
    session: Session,
) -> None:
    member = make_actor("MEMBER")
    manager = make_actor("MANAGER")
    other_mgr = make_actor("MANAGER")

    # Project 1: ACTIVE. manager is PROJECT_MANAGER,
    # other_mgr is PROJECT_MANAGER, member is CONTRIBUTOR.
    p1 = Project(
        key="REV1",
        name="Revocation Proj 1",
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
        key="REV2",
        name="Revocation Proj 2",
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

    # Tasks in Project 1:
    # Task 1 assigned to member (overdue)
    t1 = Task(
        project_id=p1.id,
        number=1,
        title="Member Task in P1",
        status=TaskStatus.TODO,
        priority=TaskPriority.HIGH,
        assignee_employee_id=member.employee_id,
        creator_employee_id=manager.employee_id,
        due_date=date.today() - timedelta(days=1),
    )
    # Task 2 assigned to manager
    t2 = Task(
        project_id=p1.id,
        number=2,
        title="Manager Task in P1",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.MEDIUM,
        assignee_employee_id=manager.employee_id,
        creator_employee_id=manager.employee_id,
    )
    # Task in Project 2:
    # Task 3 assigned to member in P2
    t3 = Task(
        project_id=p2.id,
        number=1,
        title="Member Task in P2",
        status=TaskStatus.TODO,
        priority=TaskPriority.LOW,
        assignee_employee_id=member.employee_id,
        creator_employee_id=other_mgr.employee_id,
    )

    session.add_all([t1, t2, t3])
    session.commit()

    # 1. Baseline verification
    mem_dash = get_dashboard_metrics(session, member)
    assert mem_dash.project_metrics.total_count == 2
    assert mem_dash.assigned_task_metrics.total_count == 2  # t1 and t3
    assert mem_dash.assigned_task_metrics.overdue_count == 1  # t1
    assert len(mem_dash.recent_assigned_tasks) == 2

    mgr_dash = get_dashboard_metrics(session, manager)
    assert mgr_dash.project_metrics.total_count == 2  # p1 and p2 accessible
    assert mgr_dash.project_metrics.managed_total_count == 1  # p1 managed
    assert mgr_dash.task_metrics is not None
    assert mgr_dash.task_metrics.total_count == 2  # t1 and t2 in managed p1
    assert mgr_dash.assigned_task_metrics.total_count == 1  # t2

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
    assert mem_dash_after.assigned_task_metrics.overdue_count == 0  # t1 was overdue, now excluded
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


def test_admin_metrics_covers_entire_system(session: Session) -> None:
    admin = make_actor("ADMIN")
    user1 = make_actor("MEMBER")

    p1 = Project(
        key="P1", name="P1", status=ProjectStatus.ACTIVE, creator_employee_id=user1.employee_id
    )
    p2 = Project(
        key="P2", name="P2", status=ProjectStatus.DRAFT, creator_employee_id=user1.employee_id
    )
    p3 = Project(
        key="P3", name="P3", status=ProjectStatus.ARCHIVED, creator_employee_id=user1.employee_id
    )
    session.add_all([p1, p2, p3])
    session.flush()

    t1 = Task(
        project_id=p1.id,
        number=1,
        title="T1",
        status=TaskStatus.DONE,
        priority=TaskPriority.LOW,
        creator_employee_id=user1.employee_id,
    )
    t2 = Task(
        project_id=p2.id,
        number=1,
        title="T2",
        status=TaskStatus.CANCELLED,
        priority=TaskPriority.LOW,
        creator_employee_id=user1.employee_id,
    )
    session.add_all([t1, t2])
    session.commit()

    data = get_dashboard_metrics(session, admin)

    assert data.project_metrics.total_count == 3
    assert data.project_metrics.active_count == 1
    assert data.project_metrics.draft_count == 1
    assert data.project_metrics.archived_count == 1
    assert data.project_metrics.managed_total_count == 3

    assert data.task_metrics is not None
    assert data.task_metrics.total_count == 2
    assert data.task_metrics.done_count == 1
    assert data.task_metrics.cancelled_count == 1


def test_query_count_does_not_grow_with_scale() -> None:
    """Prove that aggregate query count is O(1) and does not scale with project or task count."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    manager = make_actor("MANAGER")

    def seed_data(s: Session, prefix: str, project_count: int, tasks_per_project: int) -> None:
        for i in range(project_count):
            p = Project(
                key=f"{prefix}{i}",
                name=f"Project {prefix}{i}",
                status=ProjectStatus.ACTIVE,
                creator_employee_id=manager.employee_id,
            )
            p.memberships.append(
                ProjectMembership(employee_id=manager.employee_id, role=ProjectRole.PROJECT_MANAGER)
            )
            s.add(p)
            s.flush()
            for j in range(tasks_per_project):
                t = Task(
                    project_id=p.id,
                    number=j + 1,
                    title=f"Task {j}",
                    status=TaskStatus.TODO,
                    priority=TaskPriority.MEDIUM,
                    assignee_employee_id=manager.employee_id if j % 2 == 0 else None,
                    creator_employee_id=manager.employee_id,
                )
                s.add(t)
        s.commit()

    # Small fixture: 2 projects, 4 tasks
    with Session(engine) as s:
        seed_data(s, "SML", 2, 2)
        queries_small = 0

        def count_queries(conn, cursor, statement, parameters, context, executemany):
            nonlocal queries_small
            queries_small += 1

        event.listen(engine, "before_cursor_execute", count_queries)
        get_dashboard_metrics(s, manager)
        event.remove(engine, "before_cursor_execute", count_queries)

    # Larger fixture: add 10 more projects with 10 tasks each
    with Session(engine) as s:
        seed_data(s, "LRG", 10, 10)
        queries_large = 0

        def count_queries_large(conn, cursor, statement, parameters, context, executemany):
            nonlocal queries_large
            queries_large += 1

        event.listen(engine, "before_cursor_execute", count_queries_large)
        get_dashboard_metrics(s, manager)
        event.remove(engine, "before_cursor_execute", count_queries_large)

    # Both small and large fixtures execute the exact same number of queries!
    assert queries_small == queries_large
    assert queries_small <= 6  # Fixed bounded count <= 6 statements


def test_api_internal_endpoint(session: Session) -> None:
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    admin = make_actor("ADMIN")

    p = Project(
        key="TEST",
        name="Test Proj",
        status=ProjectStatus.ACTIVE,
        creator_employee_id=admin.employee_id,
    )
    session.add(p)
    session.commit()

    response = client.get(
        "/internal/dashboard/metrics",
        headers={
            "X-Internal-Service-Key": settings.internal_service_key,
            "X-Actor-Employee-Id": str(admin.employee_id),
            "X-Actor-Application-Role": "ADMIN",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["project_metrics"]["total_count"] == 1
    assert payload["project_metrics"]["active_count"] == 1
    assert len(payload["recent_projects"]) == 1

    app.dependency_overrides.clear()
