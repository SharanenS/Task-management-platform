import base64
import binascii
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import Project, ProjectMembership, ProjectRole, ProjectStatus


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


def _cursor(project_id: UUID) -> str:
    return base64.urlsafe_b64encode(str(project_id).encode()).decode().rstrip("=")


def _decode_cursor(value: str) -> UUID:
    try:
        return UUID(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode())
    except (ValueError, UnicodeDecodeError, binascii.Error) as error:
        raise WorkError("INVALID_CURSOR", "The project cursor is invalid.") from error


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
    session.delete(member)
    session.commit()
    return _project(session, project.id)
