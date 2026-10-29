import base64
import binascii
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Project,
    ProjectMembership,
    ProjectRole,
    ProjectStatus,
    Task,
    TaskActivity,
    TaskActivityType,
    TaskComment,
    TaskPriority,
    TaskStatus,
    WorkOutboxEvent,
)


class WorkError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code


@dataclass(frozen=True)
class Actor:
    employee_id: UUID
    application_role: str


@dataclass(frozen=True)
class ProjectPage:
    items: list[Project]
    next_cursor: str | None
    has_next_page: bool


@dataclass(frozen=True)
class TaskPage:
    items: list[Task]
    next_cursor: str | None
    has_next_page: bool


@dataclass(frozen=True)
class CommentPage:
    items: list[TaskComment]
    next_cursor: str | None
    has_next_page: bool


@dataclass(frozen=True)
class ActivityPage:
    items: list[TaskActivity]
    next_cursor: str | None
    has_next_page: bool


def _cursor(project_id: UUID) -> str:
    return base64.urlsafe_b64encode(str(project_id).encode()).decode().rstrip("=")


def _decode_cursor(value: str) -> UUID:
    try:
        return UUID(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode())
    except (ValueError, UnicodeDecodeError, binascii.Error) as error:
        raise WorkError("INVALID_CURSOR", "The project cursor is invalid.") from error


def _decode_record_cursor(value: str, label: str) -> UUID:
    try:
        return UUID(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode())
    except (ValueError, UnicodeDecodeError, binascii.Error) as error:
        raise WorkError("INVALID_CURSOR", f"The {label} cursor is invalid.") from error


def _membership(session: Session, project_id: UUID, employee_id: UUID) -> ProjectMembership | None:
    return session.scalar(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.employee_id == employee_id,
        )
    )


def _can_view(session: Session, actor: Actor, project: Project) -> bool:
    return (
        actor.application_role == "ADMIN"
        or _membership(session, project.id, actor.employee_id) is not None
    )


def _require_manager(session: Session, actor: Actor, project: Project) -> None:
    if actor.application_role == "ADMIN":
        return
    membership = _membership(session, project.id, actor.employee_id)
    if not membership or membership.role != ProjectRole.PROJECT_MANAGER:
        raise WorkError("FORBIDDEN", "Project administration is not permitted.", 403)


def _project(session: Session, project_id: UUID, *, lock: bool = False) -> Project:
    query = (
        select(Project)
        .options(selectinload(Project.memberships))
        .where(Project.id == project_id)
        .execution_options(populate_existing=True)
    )
    if lock:
        query = query.with_for_update()
    project = session.scalar(query)
    if not project:
        raise WorkError("NOT_FOUND", "Project was not found.", 404)
    return project


def list_projects(
    session: Session,
    actor: Actor,
    *,
    first: int,
    after: str | None,
    search: str | None,
    status: ProjectStatus | None,
) -> ProjectPage:
    if first < 1 or first > 50:
        raise WorkError("INVALID_PAGE_SIZE", "Project page size must be between 1 and 50.")
    query = select(Project).options(selectinload(Project.memberships)).order_by(Project.id)
    if actor.application_role != "ADMIN":
        query = query.join(ProjectMembership).where(
            ProjectMembership.employee_id == actor.employee_id
        )
    if after:
        query = query.where(Project.id > _decode_cursor(after))
    if search and (term := search.strip().lower()):
        query = query.where(
            or_(func.lower(Project.key).contains(term), func.lower(Project.name).contains(term))
        )
    if status:
        query = query.where(Project.status == status)
    rows = list(session.scalars(query.limit(first + 1)).unique())
    has_next = len(rows) > first
    items = rows[:first]
    return ProjectPage(items, _cursor(items[-1].id) if has_next and items else None, has_next)


def get_project(session: Session, actor: Actor, project_id: UUID) -> Project:
    project = _project(session, project_id)
    if not _can_view(session, actor, project):
        raise WorkError("FORBIDDEN", "Project access is not permitted.", 403)
    return project


def create_project(
    session: Session, actor: Actor, *, key: str, name: str, description: str | None
) -> Project:
    if actor.application_role not in {"ADMIN", "MANAGER"}:
        raise WorkError("FORBIDDEN", "Project creation is not permitted.", 403)
    project = Project(
        key=key, name=name.strip(), description=description, creator_employee_id=actor.employee_id
    )
    project.memberships.append(
        ProjectMembership(employee_id=actor.employee_id, role=ProjectRole.PROJECT_MANAGER)
    )
    session.add(project)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise WorkError(
            "PROJECT_KEY_CONFLICT", "The project key is already in use.", 409
        ) from error
    session.refresh(project)
    return _project(session, project.id)


def update_project(
    session: Session,
    actor: Actor,
    project_id: UUID,
    *,
    name: str,
    description: str | None,
    expected_version: int,
) -> Project:
    project = _project(session, project_id, lock=True)
    _require_manager(session, actor, project)
    if project.status == ProjectStatus.ARCHIVED:
        raise WorkError("PROJECT_ARCHIVED", "Archived projects are read-only.", 409)
    if project.version != expected_version:
        raise WorkError("VERSION_CONFLICT", "The project changed; reload and retry.", 409)
    project.name, project.description, project.version = (
        name.strip(),
        description,
        project.version + 1,
    )
    session.commit()
    return _project(session, project.id)


def set_status(
    session: Session,
    actor: Actor,
    project_id: UUID,
    *,
    status: ProjectStatus,
    expected_version: int,
) -> Project:
    project = _project(session, project_id, lock=True)
    _require_manager(session, actor, project)
    if project.version != expected_version:
        raise WorkError("VERSION_CONFLICT", "The project changed; reload and retry.", 409)
    allowed = {
        ProjectStatus.DRAFT: {ProjectStatus.ACTIVE},
        ProjectStatus.ACTIVE: {ProjectStatus.ARCHIVED},
        ProjectStatus.ARCHIVED: {ProjectStatus.ACTIVE},
    }
    if status == project.status:
        return project
    if status not in allowed[project.status]:
        raise WorkError("INVALID_STATUS", "The project status transition is not allowed.")
    project.status, project.version = status, project.version + 1
    session.commit()
    return _project(session, project.id)


def add_member(
    session: Session, actor: Actor, project_id: UUID, employee_id: UUID, role: ProjectRole
) -> Project:
    project = _project(session, project_id, lock=True)
    _require_manager(session, actor, project)
    if project.status == ProjectStatus.ARCHIVED:
        raise WorkError("PROJECT_ARCHIVED", "Archived projects are read-only.", 409)
    session.add(ProjectMembership(project_id=project.id, employee_id=employee_id, role=role))
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise WorkError("MEMBERSHIP_CONFLICT", "The employee is already a member.", 409) from error
    return _project(session, project.id)


def change_member_role(
    session: Session, actor: Actor, project_id: UUID, employee_id: UUID, role: ProjectRole
) -> Project:
    project = _project(session, project_id, lock=True)
    _require_manager(session, actor, project)
    if project.status == ProjectStatus.ARCHIVED:
        raise WorkError("PROJECT_ARCHIVED", "Archived projects are read-only.", 409)
    member = _membership(session, project.id, employee_id)
    if not member:
        raise WorkError("NOT_FOUND", "Project membership was not found.", 404)
    if member.role == ProjectRole.PROJECT_MANAGER and role != member.role:
        managers = session.scalar(
            select(func.count())
            .select_from(ProjectMembership)
            .where(
                ProjectMembership.project_id == project.id,
                ProjectMembership.role == ProjectRole.PROJECT_MANAGER,
            )
        )
        if managers == 1:
            raise WorkError("FINAL_PROJECT_MANAGER", "A project manager must remain.", 409)
    member.role = role
    session.commit()
    return _project(session, project.id)


def remove_member(session: Session, actor: Actor, project_id: UUID, employee_id: UUID) -> Project:
    project = _project(session, project_id, lock=True)
    _require_manager(session, actor, project)
    if project.status == ProjectStatus.ARCHIVED:
        raise WorkError("PROJECT_ARCHIVED", "Archived projects are read-only.", 409)
    member = _membership(session, project.id, employee_id)
    if not member:
        raise WorkError("NOT_FOUND", "Project membership was not found.", 404)
    if member.role == ProjectRole.PROJECT_MANAGER:
        managers = session.scalar(
            select(func.count())
            .select_from(ProjectMembership)
            .where(
                ProjectMembership.project_id == project.id,
                ProjectMembership.role == ProjectRole.PROJECT_MANAGER,
            )
        )
        if managers == 1:
            raise WorkError("FINAL_PROJECT_MANAGER", "A project manager must remain.", 409)
    assigned_tasks = session.scalar(
        select(func.count())
        .select_from(Task)
        .where(Task.project_id == project.id, Task.assignee_employee_id == employee_id)
    )
    if assigned_tasks:
        raise WorkError(
            "MEMBER_HAS_ASSIGNED_TASKS",
            "Reassign the employee's tasks before removing project membership.",
            409,
        )
    session.delete(member)
    session.commit()
    return _project(session, project.id)


def _require_project_view(session: Session, actor: Actor, project: Project) -> None:
    if not _can_view(session, actor, project):
        raise WorkError("FORBIDDEN", "Task access is not permitted.", 403)


def _require_task_manager(session: Session, actor: Actor, project: Project) -> None:
    _require_manager(session, actor, project)


def _require_writable(project: Project) -> None:
    if project.status == ProjectStatus.ARCHIVED:
        raise WorkError("PROJECT_ARCHIVED", "Archived projects are read-only.", 409)


def _task(session: Session, project_id: UUID, task_id: UUID, *, lock: bool = False) -> Task:
    query = select(Task).where(Task.id == task_id, Task.project_id == project_id)
    if lock:
        query = query.with_for_update()
    task = session.scalar(query)
    if not task:
        raise WorkError("NOT_FOUND", "Task was not found.", 404)
    return task


def _activity(
    session: Session,
    task: Task,
    actor: Actor,
    activity_type: TaskActivityType,
    change_data: dict[str, str | int | None],
) -> None:
    session.add(
        TaskActivity(
            task_id=task.id,
            actor_employee_id=actor.employee_id,
            activity_type=activity_type,
            change_data=change_data,
        )
    )


def list_tasks(
    session: Session,
    actor: Actor,
    project_id: UUID,
    *,
    first: int,
    after: str | None,
    search: str | None,
    status: TaskStatus | None,
    priority: TaskPriority | None,
    assignee_employee_id: UUID | None,
    unassigned: bool,
) -> TaskPage:
    if first < 1 or first > 50:
        raise WorkError("INVALID_PAGE_SIZE", "Task page size must be between 1 and 50.")
    project = _project(session, project_id)
    _require_project_view(session, actor, project)
    query = select(Task).where(Task.project_id == project.id).order_by(Task.id)
    if after:
        query = query.where(Task.id > _decode_record_cursor(after, "task"))
    if search and (term := search.strip().lower()):
        query = query.where(
            or_(func.lower(Task.title).contains(term), func.lower(Task.description).contains(term))
        )
    if status:
        query = query.where(Task.status == status)
    if priority:
        query = query.where(Task.priority == priority)
    if unassigned:
        query = query.where(Task.assignee_employee_id.is_(None))
    elif assignee_employee_id:
        query = query.where(Task.assignee_employee_id == assignee_employee_id)
    rows = list(session.scalars(query.limit(first + 1)))
    has_next = len(rows) > first
    items = rows[:first]
    return TaskPage(items, _cursor(items[-1].id) if has_next and items else None, has_next)


def task_board(
    session: Session, actor: Actor, project_id: UUID, *, lane_size: int
) -> dict[TaskStatus, tuple[list[Task], bool]]:
    if lane_size < 1 or lane_size > 25:
        raise WorkError("INVALID_PAGE_SIZE", "Board lane size must be between 1 and 25.")
    project = _project(session, project_id)
    _require_project_view(session, actor, project)
    result: dict[TaskStatus, tuple[list[Task], bool]] = {}
    for status in TaskStatus:
        rows = list(
            session.scalars(
                select(Task)
                .where(Task.project_id == project.id, Task.status == status)
                .order_by(Task.id)
                .limit(lane_size + 1)
            )
        )
        result[status] = (rows[:lane_size], len(rows) > lane_size)
    return result


def get_task(session: Session, actor: Actor, project_id: UUID, task_id: UUID) -> Task:
    project = _project(session, project_id)
    _require_project_view(session, actor, project)
    return _task(session, project.id, task_id)


def create_task(
    session: Session,
    actor: Actor,
    project_id: UUID,
    *,
    title: str,
    description: str | None,
    priority: TaskPriority,
    assignee_employee_id: UUID | None,
    due_date: date | None,
) -> Task:
    project = _project(session, project_id, lock=True)
    _require_project_view(session, actor, project)
    _require_writable(project)
    if assignee_employee_id and not _membership(session, project.id, assignee_employee_id):
        raise WorkError("INVALID_ASSIGNEE", "The assignee is not an eligible project member.")
    task = Task(
        project_id=project.id,
        number=project.next_task_number,
        title=title,
        description=description,
        priority=priority,
        assignee_employee_id=assignee_employee_id,
        creator_employee_id=actor.employee_id,
        due_date=due_date,
    )
    project.next_task_number += 1
    session.add(task)
    session.flush()
    _activity(session, task, actor, TaskActivityType.CREATED, {"version": 1})
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise WorkError("TASK_REFERENCE_CONFLICT", "The task reference conflicts.", 409) from error
    return _task(session, project.id, task.id)


def update_task(
    session: Session,
    actor: Actor,
    project_id: UUID,
    task_id: UUID,
    *,
    title: str,
    description: str | None,
    priority: TaskPriority,
    due_date: date | None,
    expected_version: int,
) -> Task:
    project = _project(session, project_id, lock=True)
    _require_task_manager(session, actor, project)
    _require_writable(project)
    task = _task(session, project.id, task_id, lock=True)
    if task.version != expected_version:
        raise WorkError("VERSION_CONFLICT", "The task changed; reload and retry.", 409)
    task.title, task.description, task.priority, task.due_date = (
        title,
        description,
        priority,
        due_date,
    )
    task.version += 1
    _activity(session, task, actor, TaskActivityType.METADATA_UPDATED, {"version": task.version})
    session.commit()
    return _task(session, project.id, task.id)


def assign_task(
    session: Session,
    actor: Actor,
    project_id: UUID,
    task_id: UUID,
    *,
    assignee_employee_id: UUID | None,
    expected_version: int,
) -> Task:
    project = _project(session, project_id, lock=True)
    _require_task_manager(session, actor, project)
    _require_writable(project)
    task = _task(session, project.id, task_id, lock=True)
    if task.version != expected_version:
        raise WorkError("VERSION_CONFLICT", "The task changed; reload and retry.", 409)
    if assignee_employee_id and not _membership(session, project.id, assignee_employee_id):
        raise WorkError("INVALID_ASSIGNEE", "The assignee is not an eligible project member.")
    previous = task.assignee_employee_id
    task.assignee_employee_id = assignee_employee_id
    task.version += 1
    _activity(
        session,
        task,
        actor,
        TaskActivityType.ASSIGNMENT_CHANGED,
        {
            "from_employee_id": str(previous) if previous else None,
            "to_employee_id": str(assignee_employee_id) if assignee_employee_id else None,
            "version": task.version,
        },
    )
    session.commit()
    return _task(session, project.id, task.id)


def change_task_status(
    session: Session,
    actor: Actor,
    project_id: UUID,
    task_id: UUID,
    *,
    status: TaskStatus,
    expected_version: int,
) -> Task:
    project = _project(session, project_id, lock=True)
    _require_project_view(session, actor, project)
    _require_writable(project)
    task = _task(session, project.id, task_id, lock=True)
    if actor.application_role != "ADMIN":
        membership = _membership(session, project.id, actor.employee_id)
        if not membership:
            raise WorkError("FORBIDDEN", "Task access is not permitted.", 403)
        if (
            membership.role != ProjectRole.PROJECT_MANAGER
            and task.assignee_employee_id != actor.employee_id
        ):
            raise WorkError("FORBIDDEN", "Only an assigned contributor may change this task.", 403)
    if task.version != expected_version:
        raise WorkError("VERSION_CONFLICT", "The task changed; reload and retry.", 409)
    allowed = {
        TaskStatus.TODO: {TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED, TaskStatus.CANCELLED},
        TaskStatus.IN_PROGRESS: {
            TaskStatus.TODO,
            TaskStatus.BLOCKED,
            TaskStatus.DONE,
            TaskStatus.CANCELLED,
        },
        TaskStatus.BLOCKED: {TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
        TaskStatus.DONE: {TaskStatus.IN_PROGRESS},
        TaskStatus.CANCELLED: {TaskStatus.TODO},
    }
    if status == task.status:
        return task
    if status not in allowed[task.status]:
        raise WorkError("INVALID_TASK_STATUS", "The task status transition is not allowed.")
    previous = task.status
    task.status = status
    task.version += 1
    _activity(
        session,
        task,
        actor,
        TaskActivityType.STATUS_CHANGED,
        {"from": previous.value, "to": status.value, "version": task.version},
    )
    if status == TaskStatus.DONE:
        session.add(
            WorkOutboxEvent(
                event_type="TASK_COMPLETED",
                schema_version=1,
                project_id=project.id,
                task_id=task.id,
                actor_employee_id=actor.employee_id,
                task_version=task.version,
            )
        )
    session.commit()
    return _task(session, project.id, task.id)


def add_task_comment(
    session: Session, actor: Actor, project_id: UUID, task_id: UUID, *, body: str
) -> TaskComment:
    project = _project(session, project_id, lock=True)
    _require_project_view(session, actor, project)
    _require_writable(project)
    task = _task(session, project.id, task_id, lock=True)
    normalized_body = body.strip()
    if not normalized_body or len(normalized_body) > 4000:
        raise WorkError("INVALID_COMMENT", "The comment must contain 1 to 4000 characters.")
    comment = TaskComment(
        task_id=task.id, author_employee_id=actor.employee_id, body=normalized_body
    )
    session.add(comment)
    session.flush()
    _activity(
        session,
        task,
        actor,
        TaskActivityType.COMMENT_ADDED,
        {"comment_id": str(comment.id)},
    )
    session.commit()
    session.refresh(comment)
    return comment


def list_task_comments(
    session: Session,
    actor: Actor,
    project_id: UUID,
    task_id: UUID,
    *,
    first: int,
    after: str | None,
) -> CommentPage:
    if first < 1 or first > 50:
        raise WorkError("INVALID_PAGE_SIZE", "Comment page size must be between 1 and 50.")
    get_task(session, actor, project_id, task_id)
    query = select(TaskComment).where(TaskComment.task_id == task_id).order_by(TaskComment.id)
    if after:
        query = query.where(TaskComment.id > _decode_record_cursor(after, "comment"))
    rows = list(session.scalars(query.limit(first + 1)))
    items = rows[:first]
    more = len(rows) > first
    return CommentPage(items, _cursor(items[-1].id) if more and items else None, more)


def list_task_activity(
    session: Session,
    actor: Actor,
    project_id: UUID,
    task_id: UUID,
    *,
    first: int,
    after: str | None,
) -> ActivityPage:
    if first < 1 or first > 50:
        raise WorkError("INVALID_PAGE_SIZE", "Activity page size must be between 1 and 50.")
    get_task(session, actor, project_id, task_id)
    query = select(TaskActivity).where(TaskActivity.task_id == task_id).order_by(TaskActivity.id)
    if after:
        query = query.where(TaskActivity.id > _decode_record_cursor(after, "activity"))
    rows = list(session.scalars(query.limit(first + 1)))
    items = rows[:first]
    more = len(rows) > first
    return ActivityPage(items, _cursor(items[-1].id) if more and items else None, more)
