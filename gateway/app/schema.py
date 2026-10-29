from datetime import date, datetime
from enum import StrEnum
from typing import NoReturn, cast

import strawberry
from graphql import GraphQLError
from strawberry.extensions import MaxAliasesLimiter, QueryDepthLimiter
from strawberry.scalars import JSON
from strawberry.types import Info

from app.auth import AuthenticationError, token_validator
from app.config import settings
from app.employee_client import EligibleEmployee as EligibleEmployeeProfile
from app.employee_client import (
    EmployeeAdminProfile,
    EmployeeDomainError,
    EmployeeForbiddenError,
    EmployeeProfile,
    EmployeeUnavailableError,
    get_admin_employee,
    get_employee,
    list_admin_employees,
    list_eligible_employees,
    provision_admin_employee,
    reconcile_admin_employee,
    resolve_employee_references,
    update_admin_employee_active,
    update_admin_employee_role,
    validate_eligible_employee,
)
from app.job_client import (
    JobDomainError,
    JobRecord,
    JobUnavailableError,
)
from app.job_client import (
    dispatch_job as job_dispatch_job,
)
from app.job_client import (
    get_job as job_get_job,
)
from app.job_client import (
    list_attempts as job_list_attempts,
)
from app.job_client import (
    list_jobs as job_list_jobs,
)
from app.job_client import list_publications as job_list_publications
from app.job_client import retry_job as job_retry_job
from app.job_client import (
    submit_job as job_submit_job,
)
from app.work_client import (
    WorkDomainError,
    WorkMembership,
    WorkProject,
    WorkTask,
    WorkUnavailableError,
)
from app.work_client import (
    add_member as work_add_member,
)
from app.work_client import (
    add_task_comment as work_add_task_comment,
)
from app.work_client import (
    assign_task as work_assign_task,
)
from app.work_client import (
    change_member_role as work_change_member_role,
)
from app.work_client import (
    change_status as work_change_status,
)
from app.work_client import (
    change_task_status as work_change_task_status,
)
from app.work_client import (
    create_project as work_create_project,
)
from app.work_client import (
    create_task as work_create_task,
)
from app.work_client import (
    get_project as work_get_project,
)
from app.work_client import (
    get_task as work_get_task,
)
from app.work_client import (
    list_projects as work_list_projects,
)
from app.work_client import (
    list_task_activity as work_list_task_activity,
)
from app.work_client import (
    list_task_comments as work_list_task_comments,
)
from app.work_client import (
    list_tasks as work_list_tasks,
)
from app.work_client import (
    remove_member as work_remove_member,
)
from app.work_client import (
    task_board as work_task_board,
)
from app.work_client import (
    update_project as work_update_project,
)
from app.work_client import (
    update_task as work_update_task,
)
from app.workflow_client import Execution as WorkflowExecutionRecord
from app.workflow_client import Rule as WorkflowRuleRecord
from app.workflow_client import WorkflowDomainError, WorkflowUnavailableError
from app.workflow_client import create_rule as workflow_create_rule
from app.workflow_client import get_execution as workflow_get_execution
from app.workflow_client import get_rule as workflow_get_rule
from app.workflow_client import list_executions as workflow_list_executions
from app.workflow_client import list_rules as workflow_list_rules
from app.workflow_client import update_rule as workflow_update_rule


@strawberry.type
class SystemInfo:
    name: str
    version: str
    environment: str
    status: str


@strawberry.enum
class ApplicationRole(StrEnum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    MEMBER = "MEMBER"


@strawberry.enum
class ProvisioningStatus(StrEnum):
    COMPLETE = "COMPLETE"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


@strawberry.enum
class ProjectStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


@strawberry.enum
class ProjectRole(StrEnum):
    PROJECT_MANAGER = "PROJECT_MANAGER"
    CONTRIBUTOR = "CONTRIBUTOR"


@strawberry.enum
class TaskStatus(StrEnum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


@strawberry.enum
class TaskPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


@strawberry.enum
class TaskActivityType(StrEnum):
    CREATED = "CREATED"
    METADATA_UPDATED = "METADATA_UPDATED"
    ASSIGNMENT_CHANGED = "ASSIGNMENT_CHANGED"
    STATUS_CHANGED = "STATUS_CHANGED"
    COMMENT_ADDED = "COMMENT_ADDED"


@strawberry.enum
class JobType(StrEnum):
    PROJECT_TASK_EXPORT = "PROJECT_TASK_EXPORT"


@strawberry.enum
class JobStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@strawberry.enum
class JobAttemptStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    ABANDONED = "ABANDONED"


@strawberry.enum
class PublicationStatus(StrEnum):
    PENDING = "PENDING"
    IN_FLIGHT = "IN_FLIGHT"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


@strawberry.enum
class WorkflowTriggerType(StrEnum):
    TASK_COMPLETED = "TASK_COMPLETED"


@strawberry.enum
class WorkflowActionType(StrEnum):
    PROJECT_TASK_EXPORT = "PROJECT_TASK_EXPORT"


@strawberry.enum
class WorkflowExecutionStatus(StrEnum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@strawberry.type
class Employee:
    id: strawberry.ID
    display_name: str
    email: str
    role: ApplicationRole


@strawberry.type
class AdminEmployee:
    id: strawberry.ID
    username: str
    display_name: str
    email: str
    role: ApplicationRole
    active: bool
    provisioning_status: ProvisioningStatus
    created_at: datetime
    updated_at: datetime
    version: int


@strawberry.type
class PageInfo:
    has_next_page: bool
    end_cursor: str | None


@strawberry.type
class EmployeeConnection:
    nodes: list[AdminEmployee]
    page_info: PageInfo


@strawberry.type
class EligibleEmployee:
    id: strawberry.ID
    display_name: str
    email: str


@strawberry.type
class EligibleEmployeeConnection:
    nodes: list[EligibleEmployee]
    page_info: PageInfo


@strawberry.type
class ProjectMembership:
    id: strawberry.ID
    employee_id: strawberry.ID
    role: ProjectRole
    created_at: datetime
    display_name: str | None
    email: str | None


@strawberry.type
class Project:
    id: strawberry.ID
    key: str
    name: str
    description: str | None
    status: ProjectStatus
    creator_employee_id: strawberry.ID
    version: int
    created_at: datetime
    updated_at: datetime
    memberships: list[ProjectMembership]


@strawberry.type
class ProjectConnection:
    nodes: list[Project]
    page_info: PageInfo


@strawberry.type
class Task:
    id: strawberry.ID
    project_id: strawberry.ID
    reference: str
    number: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    assignee_employee_id: strawberry.ID | None
    assignee_display_name: str | None
    creator_employee_id: strawberry.ID
    due_date: date | None
    version: int
    created_at: datetime
    updated_at: datetime


@strawberry.type
class TaskConnection:
    nodes: list[Task]
    page_info: PageInfo


@strawberry.type
class TaskBoardLane:
    status: TaskStatus
    tasks: list[Task]
    has_more: bool


@strawberry.type
class TaskBoard:
    lanes: list[TaskBoardLane]


@strawberry.type
class TaskComment:
    id: strawberry.ID
    task_id: strawberry.ID
    author_employee_id: strawberry.ID
    author_display_name: str | None
    body: str
    created_at: datetime


@strawberry.type
class TaskCommentConnection:
    nodes: list[TaskComment]
    page_info: PageInfo


@strawberry.type
class TaskActivity:
    id: strawberry.ID
    task_id: strawberry.ID
    actor_employee_id: strawberry.ID
    actor_display_name: str | None
    activity_type: TaskActivityType
    change_data: JSON
    created_at: datetime


@strawberry.type
class TaskActivityConnection:
    nodes: list[TaskActivity]
    page_info: PageInfo


@strawberry.type
class ProjectTaskExportPayload:
    project_id: strawberry.ID
    format: str
    include_completed: bool


@strawberry.type
class JobAttempt:
    id: strawberry.ID
    attempt_number: int
    status: JobAttemptStatus
    started_at: datetime
    finished_at: datetime | None
    failure_code: str | None
    retryable: bool
    safe_summary: str | None
    lease_acquired_at: datetime | None
    lease_expires_at: datetime | None
    last_heartbeat_at: datetime | None
    abandoned_at: datetime | None
    retry_scheduled_at: datetime | None
    recovered_at: datetime | None


@strawberry.type
class JobPublication:
    id: strawberry.ID
    status: PublicationStatus
    attempt_count: int
    next_retry_at: datetime | None
    lease_expires_at: datetime | None
    published_at: datetime | None
    last_failure_classification: str | None
    reconciliation_required: bool


@strawberry.type
class Job:
    id: strawberry.ID
    job_type: JobType
    status: JobStatus
    submitter_employee_id: strawberry.ID
    payload: ProjectTaskExportPayload
    result_summary: str | None
    result_content: str | None
    result_content_type: str | None
    result_checksum: str | None
    result_row_count: int | None
    result_truncated: bool | None
    failure_classification: str | None
    completed_at: datetime | None
    execution_generation: int
    retry_exhausted: bool
    manual_retry_count: int
    version: int
    created_at: datetime
    updated_at: datetime
    attempts: list[JobAttempt]
    publication: JobPublication | None


@strawberry.type
class JobConnection:
    nodes: list[Job]
    page_info: PageInfo


@strawberry.type
class PublicationConnection:
    nodes: list[JobPublication]
    page_info: PageInfo


@strawberry.type
class WorkflowRule:
    id: strawberry.ID
    project_id: strawberry.ID
    name: str
    trigger_type: WorkflowTriggerType
    action_type: WorkflowActionType
    enabled: bool
    creator_employee_id: strawberry.ID
    version: int
    created_at: datetime
    updated_at: datetime


@strawberry.type
class WorkflowRuleConnection:
    nodes: list[WorkflowRule]
    page_info: PageInfo


@strawberry.type
class WorkflowExecution:
    id: strawberry.ID
    rule_id: strawberry.ID
    source_event_id: strawberry.ID
    project_id: strawberry.ID
    task_id: strawberry.ID
    status: WorkflowExecutionStatus
    resulting_job_id: strawberry.ID | None
    failure_classification: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


@strawberry.type
class WorkflowExecutionConnection:
    nodes: list[WorkflowExecution]
    page_info: PageInfo


@strawberry.input
class ProvisionEmployeeInput:
    idempotency_key: str
    username: str
    email: str
    display_name: str
    role: ApplicationRole
    active: bool
    temporary_password: str


@strawberry.input
class CreateProjectInput:
    key: str
    name: str
    description: str | None = None


@strawberry.input
class UpdateProjectInput:
    name: str
    description: str | None
    expected_version: int


@strawberry.input
class CreateTaskInput:
    title: str
    description: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_employee_id: strawberry.ID | None = None
    due_date: date | None = None


@strawberry.input
class UpdateTaskInput:
    title: str
    description: str | None
    priority: TaskPriority
    due_date: date | None
    expected_version: int


@strawberry.input
class SubmitProjectTaskExportInput:
    project_id: strawberry.ID
    include_completed: bool = True
    idempotency_key: str


@strawberry.input
class CreateWorkflowRuleInput:
    project_id: strawberry.ID
    name: str
    trigger_type: WorkflowTriggerType
    action_type: WorkflowActionType
    enabled: bool = True


@strawberry.input
class UpdateWorkflowRuleInput:
    name: str
    expected_version: int


def _admin_employee(profile: EmployeeAdminProfile) -> AdminEmployee:
    return AdminEmployee(
        id=strawberry.ID(profile.id),
        username=profile.username,
        display_name=profile.display_name,
        email=profile.email,
        role=ApplicationRole(profile.role),
        active=profile.active,
        provisioning_status=ProvisioningStatus(profile.provisioning_status),
        created_at=datetime.fromisoformat(profile.created_at),
        updated_at=datetime.fromisoformat(profile.updated_at),
        version=profile.version,
    )


def _project_membership(
    member: WorkMembership, profiles: dict[str, EligibleEmployeeProfile]
) -> ProjectMembership:
    profile = profiles.get(member.employee_id)
    return ProjectMembership(
        id=strawberry.ID(member.id),
        employee_id=strawberry.ID(member.employee_id),
        role=ProjectRole(member.role),
        created_at=datetime.fromisoformat(member.created_at),
        display_name=profile.display_name if profile else None,
        email=profile.email if profile else None,
    )


def _project(
    value: WorkProject, profiles: dict[str, EligibleEmployeeProfile] | None = None
) -> Project:
    profiles = profiles or {}
    return Project(
        id=strawberry.ID(value.id),
        key=value.key,
        name=value.name,
        description=value.description,
        status=ProjectStatus(value.status),
        creator_employee_id=strawberry.ID(value.creator_employee_id),
        version=value.version,
        created_at=datetime.fromisoformat(value.created_at),
        updated_at=datetime.fromisoformat(value.updated_at),
        memberships=[_project_membership(member, profiles) for member in value.memberships],
    )


async def _enriched_projects(subject: str, values: list[WorkProject]) -> list[Project]:
    employee_ids = list(
        dict.fromkeys(member.employee_id for project in values for member in project.memberships)
    )
    profiles = {
        profile.id: profile
        for profile in (
            await resolve_employee_references(subject, employee_ids) if employee_ids else []
        )
    }
    return [_project(value, profiles) for value in values]


async def _enriched_project(subject: str, value: WorkProject) -> Project:
    return (await _enriched_projects(subject, [value]))[0]


def _task_value(
    value: WorkTask,
    project_key: str,
    profiles: dict[str, EligibleEmployeeProfile],
) -> Task:
    assignee = profiles.get(value.assignee_employee_id or "")
    return Task(
        id=strawberry.ID(value.id),
        project_id=strawberry.ID(value.project_id),
        reference=f"{project_key}-{value.number}",
        number=value.number,
        title=value.title,
        description=value.description,
        status=TaskStatus(value.status),
        priority=TaskPriority(value.priority),
        assignee_employee_id=(
            strawberry.ID(value.assignee_employee_id) if value.assignee_employee_id else None
        ),
        assignee_display_name=assignee.display_name if assignee else None,
        creator_employee_id=strawberry.ID(value.creator_employee_id),
        due_date=date.fromisoformat(value.due_date) if value.due_date else None,
        version=value.version,
        created_at=datetime.fromisoformat(value.created_at),
        updated_at=datetime.fromisoformat(value.updated_at),
    )


async def _enriched_tasks(subject: str, project: WorkProject, values: list[WorkTask]) -> list[Task]:
    employee_ids = list(
        dict.fromkeys(value.assignee_employee_id for value in values if value.assignee_employee_id)
    )
    profiles = {
        profile.id: profile
        for profile in (
            await resolve_employee_references(subject, employee_ids) if employee_ids else []
        )
    }
    return [_task_value(value, project.key, profiles) for value in values]


async def _enriched_task(subject: str, actor: EmployeeProfile, value: WorkTask) -> Task:
    project = await work_get_project(actor, value.project_id)
    return (await _enriched_tasks(subject, project, [value]))[0]


def _job_value(value: JobRecord, attempts: list[JobAttempt] | None = None) -> Job:
    try:
        project_id = value.payload["projectId"]
        format_value = value.payload["format"]
        include_completed = value.payload["includeCompleted"]
        if (
            not isinstance(project_id, str)
            or format_value != "CSV"
            or not isinstance(include_completed, bool)
        ):
            raise ValueError
        payload = ProjectTaskExportPayload(
            project_id=strawberry.ID(project_id),
            format=format_value,
            include_completed=include_completed,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise JobUnavailableError from error
    publication = None
    if value.publication:
        item = value.publication
        publication = JobPublication(
            id=strawberry.ID(str(item["id"])),
            status=PublicationStatus(str(item["status"])),
            attempt_count=int(item["attempt_count"]),
            next_retry_at=datetime.fromisoformat(str(item["available_at"]))
            if item.get("available_at")
            else None,
            lease_expires_at=datetime.fromisoformat(str(item["lease_expires_at"]))
            if item.get("lease_expires_at")
            else None,
            published_at=datetime.fromisoformat(str(item["published_at"]))
            if item.get("published_at")
            else None,
            last_failure_classification=item.get("last_failure_classification"),
            reconciliation_required=bool(item.get("reconciliation_required")),
        )
    return Job(
        id=strawberry.ID(value.id),
        job_type=JobType(value.job_type),
        status=JobStatus(value.status),
        submitter_employee_id=strawberry.ID(value.submitter_employee_id),
        payload=payload,
        result_summary=value.result_summary,
        result_content=value.result_content,
        result_content_type=value.result_content_type,
        result_checksum=value.result_checksum,
        result_row_count=value.result_row_count,
        result_truncated=value.result_truncated,
        failure_classification=value.failure_classification,
        completed_at=datetime.fromisoformat(value.completed_at) if value.completed_at else None,
        execution_generation=value.execution_generation,
        retry_exhausted=value.retry_exhausted,
        manual_retry_count=value.manual_retry_count,
        version=value.version,
        created_at=datetime.fromisoformat(value.created_at),
        updated_at=datetime.fromisoformat(value.updated_at),
        attempts=attempts or [],
        publication=publication,
    )


async def _project_actor(info: Info) -> tuple[str, EmployeeProfile]:
    try:
        identity = token_validator.validate(info.context["authorization"])
    except AuthenticationError as error:
        raise GraphQLError(
            "Authentication is required.", extensions={"code": "UNAUTHENTICATED"}
        ) from error
    try:
        return identity.subject, await get_employee(identity.subject)
    except EmployeeForbiddenError as error:
        raise GraphQLError(
            "Project access is not available for this account.", extensions={"code": "FORBIDDEN"}
        ) from error
    except EmployeeUnavailableError as error:
        raise GraphQLError(
            "Project access is temporarily unavailable.",
            extensions={"code": "SERVICE_UNAVAILABLE"},
        ) from error


def _raise_project_error(error: Exception) -> NoReturn:
    if isinstance(error, WorkDomainError):
        raise GraphQLError(error.message, extensions={"code": error.code}) from error
    if isinstance(error, (WorkUnavailableError, EmployeeUnavailableError)):
        raise GraphQLError(
            "Project management is temporarily unavailable.",
            extensions={"code": "SERVICE_UNAVAILABLE"},
        ) from error
    if isinstance(error, EmployeeDomainError):
        raise GraphQLError(error.message, extensions={"code": error.code}) from error
    raise error


def _raise_job_error(error: Exception) -> NoReturn:
    if isinstance(error, JobDomainError):
        messages = {
            "IDEMPOTENCY_CONFLICT": "The idempotency key is already in use.",
            "INVALID_CURSOR": "The job cursor is invalid.",
            "INVALID_PAGE_SIZE": "The page size must be between 1 and 50.",
            "JOB_NOT_FOUND": "The job was not found.",
            "INVALID_INPUT": "The job input is invalid.",
            "VERSION_CONFLICT": "The job changed before it could be dispatched.",
            "JOB_NOT_DISPATCHABLE": "The job cannot be dispatched in its current state.",
            "JOB_NOT_RETRYABLE": "The job is not eligible for administrative retry.",
            "JOB_RETRY_CONFLICT": "The retry request conflicted. Refresh and try again.",
            "BROKER_UNAVAILABLE": "Job dispatch is temporarily unavailable.",
        }
        message = messages.get(error.code)
        if message is None:
            raise GraphQLError(
                "Job management is temporarily unavailable.",
                extensions={"code": "SERVICE_UNAVAILABLE"},
            ) from error
        raise GraphQLError(message, extensions={"code": error.code}) from error
    if isinstance(error, (JobUnavailableError, EmployeeUnavailableError, WorkUnavailableError)):
        raise GraphQLError(
            "Job management is temporarily unavailable.",
            extensions={"code": "SERVICE_UNAVAILABLE"},
        ) from error
    if isinstance(error, WorkDomainError):
        raise GraphQLError(
            "The referenced project is unavailable.", extensions={"code": error.code}
        ) from error
    raise error


async def _admin_subject(info: Info) -> str:
    try:
        identity = token_validator.validate(info.context["authorization"])
    except AuthenticationError as error:
        raise GraphQLError(
            "Authentication is required.", extensions={"code": "UNAUTHENTICATED"}
        ) from error
    try:
        actor = await get_employee(identity.subject)
    except EmployeeForbiddenError as error:
        raise GraphQLError(
            "Administrator access is required.", extensions={"code": "FORBIDDEN"}
        ) from error
    except EmployeeUnavailableError as error:
        raise GraphQLError(
            "Employee administration is temporarily unavailable.",
            extensions={"code": "SERVICE_UNAVAILABLE"},
        ) from error
    if actor.role != ApplicationRole.ADMIN:
        raise GraphQLError("Administrator access is required.", extensions={"code": "FORBIDDEN"})
    return identity.subject


def _raise_admin_error(error: Exception) -> NoReturn:
    if isinstance(error, EmployeeDomainError):
        raise GraphQLError(error.message, extensions={"code": error.code}) from error
    if isinstance(error, EmployeeUnavailableError):
        raise GraphQLError(
            "Employee administration is temporarily unavailable.",
            extensions={"code": "SERVICE_UNAVAILABLE"},
        ) from error
    raise error


def _workflow_rule(value: WorkflowRuleRecord) -> WorkflowRule:
    return WorkflowRule(
        id=strawberry.ID(value.id),
        project_id=strawberry.ID(value.project_id),
        name=value.name,
        trigger_type=WorkflowTriggerType(value.trigger_type),
        action_type=WorkflowActionType(value.action_type),
        enabled=value.enabled,
        creator_employee_id=strawberry.ID(value.creator_employee_id),
        version=value.version,
        created_at=datetime.fromisoformat(value.created_at),
        updated_at=datetime.fromisoformat(value.updated_at),
    )


def _workflow_execution(value: WorkflowExecutionRecord) -> WorkflowExecution:
    return WorkflowExecution(
        id=strawberry.ID(value.id),
        rule_id=strawberry.ID(value.rule_id),
        source_event_id=strawberry.ID(value.source_event_id),
        project_id=strawberry.ID(value.project_id),
        task_id=strawberry.ID(value.task_id),
        status=WorkflowExecutionStatus(value.status),
        resulting_job_id=strawberry.ID(value.resulting_job_id) if value.resulting_job_id else None,
        failure_classification=value.failure_classification,
        created_at=datetime.fromisoformat(value.created_at),
        updated_at=datetime.fromisoformat(value.updated_at),
        completed_at=datetime.fromisoformat(value.completed_at) if value.completed_at else None,
    )


async def _workflow_actor(info: Info) -> tuple[EmployeeProfile, list[str], list[str]]:
    _, actor = await _project_actor(info)
    project_ids: list[str] = []
    managed: list[str] = []
    cursor: str | None = None
    while True:
        page = await work_list_projects(actor, first=50, after=cursor, search=None, status=None)
        for project in page.items:
            project_ids.append(project.id)
            if actor.role == "ADMIN" or any(
                member.employee_id == actor.id and member.role == "PROJECT_MANAGER"
                for member in project.memberships
            ):
                managed.append(project.id)
        if not page.has_next_page or not page.next_cursor:
            break
        cursor = page.next_cursor
    return actor, project_ids, managed


def _raise_workflow_error(error: Exception) -> NoReturn:
    if isinstance(error, WorkflowDomainError):
        messages = {
            "NOT_FOUND": "The workflow was not found.",
            "FORBIDDEN": "Workflow access is not permitted.",
            "VERSION_CONFLICT": "The workflow changed; reload and retry.",
            "INVALID_CURSOR": "The workflow cursor is invalid.",
            "INVALID_PAGE_SIZE": "The workflow page size is invalid.",
        }
        raise GraphQLError(
            messages.get(error.code, "The workflow request could not be completed."),
            extensions={"code": error.code},
        ) from error
    if isinstance(
        error, (WorkflowUnavailableError, WorkUnavailableError, EmployeeUnavailableError)
    ):
        raise GraphQLError(
            "Workflow automation is temporarily unavailable.",
            extensions={"code": "SERVICE_UNAVAILABLE"},
        ) from error
    raise error


@strawberry.type
class Query:
    @strawberry.field
    def system_info(self) -> SystemInfo:
        """Public, non-sensitive gateway metadata; not aggregate service health."""
        return SystemInfo(
            name="Enterprise Task Platform Gateway",
            version="0.1.0",
            environment=settings.app_env,
            status="AVAILABLE",
        )

    @strawberry.field
    async def me(self, info: Info) -> Employee:
        try:
            identity = token_validator.validate(info.context["authorization"])
        except AuthenticationError as error:
            raise GraphQLError(
                "Authentication is required.", extensions={"code": "UNAUTHENTICATED"}
            ) from error
        try:
            profile = await get_employee(identity.subject)
        except EmployeeForbiddenError as error:
            raise GraphQLError(
                "Access is not available for this account.",
                extensions={"code": "FORBIDDEN"},
            ) from error
        except EmployeeUnavailableError as error:
            raise GraphQLError(
                "Employee profiles are temporarily unavailable.",
                extensions={"code": "SERVICE_UNAVAILABLE"},
            ) from error
        return Employee(
            id=strawberry.ID(profile.id),
            display_name=profile.display_name,
            email=profile.email,
            role=ApplicationRole(profile.role),
        )

    @strawberry.field
    async def workflow_rules(
        self,
        info: Info,
        first: int = 20,
        after: str | None = None,
        project_id: strawberry.ID | None = None,
        enabled: bool | None = None,
    ) -> WorkflowRuleConnection:
        try:
            actor, projects, managed = await _workflow_actor(info)
            page = await workflow_list_rules(
                actor,
                projects,
                managed,
                first=first,
                after=after,
                project_id=str(project_id) if project_id else None,
                enabled=enabled,
            )
            return WorkflowRuleConnection(
                nodes=[_workflow_rule(item) for item in page.items],
                page_info=PageInfo(has_next_page=page.has_next_page, end_cursor=page.next_cursor),
            )
        except (
            WorkflowDomainError,
            WorkflowUnavailableError,
            WorkUnavailableError,
            EmployeeUnavailableError,
        ) as error:
            _raise_workflow_error(error)

    @strawberry.field
    async def workflow_rule(self, info: Info, id: strawberry.ID) -> WorkflowRule:
        try:
            actor, projects, managed = await _workflow_actor(info)
            return _workflow_rule(await workflow_get_rule(actor, str(id), projects, managed))
        except (
            WorkflowDomainError,
            WorkflowUnavailableError,
            WorkUnavailableError,
            EmployeeUnavailableError,
        ) as error:
            _raise_workflow_error(error)

    @strawberry.field
    async def workflow_executions(
        self,
        info: Info,
        first: int = 20,
        after: str | None = None,
        rule_id: strawberry.ID | None = None,
    ) -> WorkflowExecutionConnection:
        try:
            actor, projects, managed = await _workflow_actor(info)
            page = await workflow_list_executions(
                actor,
                projects,
                managed,
                first=first,
                after=after,
                rule_id=str(rule_id) if rule_id else None,
            )
            return WorkflowExecutionConnection(
                nodes=[_workflow_execution(item) for item in page.items],
                page_info=PageInfo(has_next_page=page.has_next_page, end_cursor=page.next_cursor),
            )
        except (
            WorkflowDomainError,
            WorkflowUnavailableError,
            WorkUnavailableError,
            EmployeeUnavailableError,
        ) as error:
            _raise_workflow_error(error)

    @strawberry.field
    async def workflow_execution(self, info: Info, id: strawberry.ID) -> WorkflowExecution:
        try:
            actor, projects, managed = await _workflow_actor(info)
            return _workflow_execution(
                await workflow_get_execution(actor, str(id), projects, managed)
            )
        except (
            WorkflowDomainError,
            WorkflowUnavailableError,
            WorkUnavailableError,
            EmployeeUnavailableError,
        ) as error:
            _raise_workflow_error(error)

    @strawberry.field
    async def jobs(
        self,
        info: Info,
        first: int = 20,
        after: str | None = None,
        status: JobStatus | None = None,
        job_type: JobType | None = None,
    ) -> JobConnection:
        _, actor = await _project_actor(info)
        try:
            page = await job_list_jobs(
                actor,
                first=first,
                after=after,
                status=status.value if status else None,
                job_type=job_type.value if job_type else None,
            )
            return JobConnection(
                nodes=[_job_value(value) for value in page.items],
                page_info=PageInfo(has_next_page=page.has_next_page, end_cursor=page.next_cursor),
            )
        except (JobDomainError, JobUnavailableError, EmployeeUnavailableError) as error:
            _raise_job_error(error)

    @strawberry.field
    async def job_publications(
        self,
        info: Info,
        first: int = 20,
        after: str | None = None,
        status: PublicationStatus | None = None,
    ) -> PublicationConnection:
        _, actor = await _project_actor(info)
        if actor.role != "ADMIN":
            raise GraphQLError(
                "Administrator access is required.", extensions={"code": "FORBIDDEN"}
            )
        try:
            page = await job_list_publications(
                actor,
                first=first,
                after=after,
                status=status.value if status else None,
            )
            return PublicationConnection(
                nodes=[
                    JobPublication(
                        id=strawberry.ID(item.id),
                        status=PublicationStatus(item.status),
                        attempt_count=item.attempt_count,
                        next_retry_at=datetime.fromisoformat(item.available_at),
                        lease_expires_at=(
                            datetime.fromisoformat(item.lease_expires_at)
                            if item.lease_expires_at
                            else None
                        ),
                        published_at=(
                            datetime.fromisoformat(item.published_at) if item.published_at else None
                        ),
                        last_failure_classification=item.last_failure_classification,
                        reconciliation_required=item.reconciliation_required,
                    )
                    for item in page.items
                ],
                page_info=PageInfo(has_next_page=page.has_next_page, end_cursor=page.next_cursor),
            )
        except (JobDomainError, JobUnavailableError, EmployeeUnavailableError) as error:
            _raise_job_error(error)

    @strawberry.field
    async def job(self, info: Info, id: strawberry.ID) -> Job:
        _, actor = await _project_actor(info)
        try:
            value = await job_get_job(actor, str(id))
            attempts = await job_list_attempts(actor, str(id))
            return _job_value(
                value,
                [
                    JobAttempt(
                        id=strawberry.ID(attempt.id),
                        attempt_number=attempt.attempt_number,
                        status=JobAttemptStatus(attempt.status),
                        started_at=datetime.fromisoformat(attempt.started_at),
                        finished_at=(
                            datetime.fromisoformat(attempt.finished_at)
                            if attempt.finished_at
                            else None
                        ),
                        failure_code=attempt.failure_code,
                        retryable=attempt.retryable,
                        safe_summary=attempt.safe_summary,
                        lease_acquired_at=(
                            datetime.fromisoformat(attempt.lease_acquired_at)
                            if attempt.lease_acquired_at
                            else None
                        ),
                        lease_expires_at=(
                            datetime.fromisoformat(attempt.lease_expires_at)
                            if attempt.lease_expires_at
                            else None
                        ),
                        last_heartbeat_at=(
                            datetime.fromisoformat(attempt.last_heartbeat_at)
                            if attempt.last_heartbeat_at
                            else None
                        ),
                        abandoned_at=(
                            datetime.fromisoformat(attempt.abandoned_at)
                            if attempt.abandoned_at
                            else None
                        ),
                        retry_scheduled_at=(
                            datetime.fromisoformat(attempt.retry_scheduled_at)
                            if attempt.retry_scheduled_at
                            else None
                        ),
                        recovered_at=(
                            datetime.fromisoformat(attempt.recovered_at)
                            if attempt.recovered_at
                            else None
                        ),
                    )
                    for attempt in attempts
                ],
            )
        except (JobDomainError, JobUnavailableError, EmployeeUnavailableError) as error:
            _raise_job_error(error)

    @strawberry.field
    async def employees(
        self,
        info: Info,
        first: int = 20,
        after: str | None = None,
        search: str | None = None,
        role: ApplicationRole | None = None,
        active: bool | None = None,
    ) -> EmployeeConnection:
        subject = await _admin_subject(info)
        try:
            page = await list_admin_employees(
                subject,
                first=first,
                after=after,
                search=search,
                role=role.value if role else None,
                active=active,
            )
        except (EmployeeDomainError, EmployeeUnavailableError) as error:
            _raise_admin_error(error)
        return EmployeeConnection(
            nodes=[_admin_employee(employee) for employee in page.items],
            page_info=PageInfo(has_next_page=page.has_next_page, end_cursor=page.next_cursor),
        )

    @strawberry.field
    async def employee(self, info: Info, id: strawberry.ID) -> AdminEmployee:
        subject = await _admin_subject(info)
        try:
            return _admin_employee(await get_admin_employee(subject, str(id)))
        except (EmployeeDomainError, EmployeeUnavailableError) as error:
            _raise_admin_error(error)

    @strawberry.field
    async def projects(
        self,
        info: Info,
        first: int = 20,
        after: str | None = None,
        search: str | None = None,
        status: ProjectStatus | None = None,
    ) -> ProjectConnection:
        subject, actor = await _project_actor(info)
        try:
            page = await work_list_projects(
                actor,
                first=first,
                after=after,
                search=search,
                status=status.value if status else None,
            )
            return ProjectConnection(
                nodes=await _enriched_projects(subject, page.items),
                page_info=PageInfo(
                    has_next_page=page.has_next_page,
                    end_cursor=page.next_cursor,
                ),
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.field
    async def project(self, info: Info, id: strawberry.ID) -> Project:
        subject, actor = await _project_actor(info)
        try:
            return await _enriched_project(subject, await work_get_project(actor, str(id)))
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.field
    async def eligible_project_members(
        self,
        info: Info,
        first: int = 20,
        after: str | None = None,
        search: str | None = None,
    ) -> EligibleEmployeeConnection:
        subject, actor = await _project_actor(info)
        if actor.role not in {"ADMIN", "MANAGER"}:
            raise GraphQLError(
                "Project membership lookup is not permitted.", extensions={"code": "FORBIDDEN"}
            )
        try:
            page = await list_eligible_employees(subject, first=first, after=after, search=search)
            return EligibleEmployeeConnection(
                nodes=[
                    EligibleEmployee(
                        id=strawberry.ID(item.id),
                        display_name=item.display_name,
                        email=item.email,
                    )
                    for item in page.items
                ],
                page_info=PageInfo(
                    has_next_page=page.has_next_page,
                    end_cursor=page.next_cursor,
                ),
            )
        except (EmployeeDomainError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.field
    async def project_tasks(
        self,
        info: Info,
        project_id: strawberry.ID,
        first: int = 20,
        after: str | None = None,
        search: str | None = None,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee_employee_id: strawberry.ID | None = None,
        unassigned: bool = False,
    ) -> TaskConnection:
        subject, actor = await _project_actor(info)
        try:
            project = await work_get_project(actor, str(project_id))
            page = await work_list_tasks(
                actor,
                str(project_id),
                params={
                    "first": first,
                    **({"after": after} if after else {}),
                    **({"search": search} if search else {}),
                    **({"status": status.value} if status else {}),
                    **({"priority": priority.value} if priority else {}),
                    **(
                        {"assignee_employee_id": str(assignee_employee_id)}
                        if assignee_employee_id
                        else {}
                    ),
                    "unassigned": unassigned,
                },
            )
            return TaskConnection(
                nodes=await _enriched_tasks(subject, project, page.items),
                page_info=PageInfo(has_next_page=page.has_next_page, end_cursor=page.next_cursor),
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.field
    async def project_task_board(
        self, info: Info, project_id: strawberry.ID, lane_size: int = 20
    ) -> TaskBoard:
        subject, actor = await _project_actor(info)
        try:
            project = await work_get_project(actor, str(project_id))
            lanes = await work_task_board(actor, str(project_id), lane_size)
            values = [task for lane in lanes for task in lane.items]
            enriched = {
                str(task.id): task for task in await _enriched_tasks(subject, project, values)
            }
            return TaskBoard(
                lanes=[
                    TaskBoardLane(
                        status=TaskStatus(lane.status),
                        tasks=[enriched[item.id] for item in lane.items],
                        has_more=lane.has_more,
                    )
                    for lane in lanes
                ]
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.field
    async def task(self, info: Info, project_id: strawberry.ID, task_id: strawberry.ID) -> Task:
        subject, actor = await _project_actor(info)
        try:
            return await _enriched_task(
                subject, actor, await work_get_task(actor, str(project_id), str(task_id))
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.field
    async def task_comments(
        self,
        info: Info,
        project_id: strawberry.ID,
        task_id: strawberry.ID,
        first: int = 20,
        after: str | None = None,
    ) -> TaskCommentConnection:
        subject, actor = await _project_actor(info)
        try:
            values, cursor, more = await work_list_task_comments(
                actor, str(project_id), str(task_id), first=first, after=after
            )
            ids = list(dict.fromkeys(value.author_employee_id for value in values))
            profiles = {
                item.id: item
                for item in (await resolve_employee_references(subject, ids) if ids else [])
            }
            return TaskCommentConnection(
                nodes=[
                    TaskComment(
                        id=strawberry.ID(value.id),
                        task_id=strawberry.ID(value.task_id),
                        author_employee_id=strawberry.ID(value.author_employee_id),
                        author_display_name=(
                            profiles[value.author_employee_id].display_name
                            if value.author_employee_id in profiles
                            else None
                        ),
                        body=value.body,
                        created_at=datetime.fromisoformat(value.created_at),
                    )
                    for value in values
                ],
                page_info=PageInfo(has_next_page=more, end_cursor=cursor),
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.field
    async def task_activity(
        self,
        info: Info,
        project_id: strawberry.ID,
        task_id: strawberry.ID,
        first: int = 20,
        after: str | None = None,
    ) -> TaskActivityConnection:
        subject, actor = await _project_actor(info)
        try:
            values, cursor, more = await work_list_task_activity(
                actor, str(project_id), str(task_id), first=first, after=after
            )
            ids = list(dict.fromkeys(value.actor_employee_id for value in values))
            profiles = {
                item.id: item
                for item in (await resolve_employee_references(subject, ids) if ids else [])
            }
            return TaskActivityConnection(
                nodes=[
                    TaskActivity(
                        id=strawberry.ID(value.id),
                        task_id=strawberry.ID(value.task_id),
                        actor_employee_id=strawberry.ID(value.actor_employee_id),
                        actor_display_name=(
                            profiles[value.actor_employee_id].display_name
                            if value.actor_employee_id in profiles
                            else None
                        ),
                        activity_type=TaskActivityType(value.activity_type),
                        change_data=cast(JSON, value.change_data),
                        created_at=datetime.fromisoformat(value.created_at),
                    )
                    for value in values
                ],
                page_info=PageInfo(has_next_page=more, end_cursor=cursor),
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_workflow_rule(
        self, info: Info, input: CreateWorkflowRuleInput
    ) -> WorkflowRule:
        try:
            actor, projects, managed = await _workflow_actor(info)
            return _workflow_rule(
                await workflow_create_rule(
                    actor,
                    {
                        "project_id": str(input.project_id),
                        "name": input.name,
                        "trigger_type": input.trigger_type.value,
                        "action_type": input.action_type.value,
                        "enabled": input.enabled,
                    },
                    projects,
                    managed,
                )
            )
        except (
            WorkflowDomainError,
            WorkflowUnavailableError,
            WorkUnavailableError,
            EmployeeUnavailableError,
        ) as error:
            _raise_workflow_error(error)

    @strawberry.mutation
    async def update_workflow_rule(
        self, info: Info, rule_id: strawberry.ID, input: UpdateWorkflowRuleInput
    ) -> WorkflowRule:
        try:
            actor, projects, managed = await _workflow_actor(info)
            return _workflow_rule(
                await workflow_update_rule(
                    actor,
                    str(rule_id),
                    {"name": input.name, "expected_version": input.expected_version},
                    projects,
                    managed,
                )
            )
        except (
            WorkflowDomainError,
            WorkflowUnavailableError,
            WorkUnavailableError,
            EmployeeUnavailableError,
        ) as error:
            _raise_workflow_error(error)

    @strawberry.mutation
    async def set_workflow_rule_enabled(
        self, info: Info, rule_id: strawberry.ID, enabled: bool, expected_version: int
    ) -> WorkflowRule:
        try:
            actor, projects, managed = await _workflow_actor(info)
            return _workflow_rule(
                await workflow_update_rule(
                    actor,
                    str(rule_id),
                    {"enabled": enabled, "expected_version": expected_version},
                    projects,
                    managed,
                    state=True,
                )
            )
        except (
            WorkflowDomainError,
            WorkflowUnavailableError,
            WorkUnavailableError,
            EmployeeUnavailableError,
        ) as error:
            _raise_workflow_error(error)

    @strawberry.mutation
    async def dispatch_job(self, info: Info, job_id: strawberry.ID, expected_version: int) -> Job:
        _, actor = await _project_actor(info)
        try:
            current = await job_get_job(actor, str(job_id))
            if current.related_project_id is None:
                raise JobDomainError("INVALID_INPUT", "The job has no project.")
            await work_get_project(actor, current.related_project_id)
            return _job_value(
                await job_dispatch_job(actor, job_id=str(job_id), expected_version=expected_version)
            )
        except (
            JobDomainError,
            JobUnavailableError,
            WorkDomainError,
            WorkUnavailableError,
            EmployeeUnavailableError,
        ) as error:
            _raise_job_error(error)

    @strawberry.mutation
    async def retry_job(self, info: Info, job_id: strawberry.ID, expected_version: int) -> Job:
        _, actor = await _project_actor(info)
        if actor.role != "ADMIN":
            raise GraphQLError(
                "Administrator access is required.", extensions={"code": "FORBIDDEN"}
            )
        try:
            return _job_value(
                await job_retry_job(actor, job_id=str(job_id), expected_version=expected_version)
            )
        except (JobDomainError, JobUnavailableError, EmployeeUnavailableError) as error:
            _raise_job_error(error)

    @strawberry.mutation
    async def submit_project_task_export(
        self, info: Info, input: SubmitProjectTaskExportInput
    ) -> Job:
        _, actor = await _project_actor(info)
        try:
            await work_get_project(actor, str(input.project_id))
            return _job_value(
                await job_submit_job(
                    actor,
                    project_id=str(input.project_id),
                    include_completed=input.include_completed,
                    idempotency_key=input.idempotency_key,
                )
            )
        except (
            JobDomainError,
            JobUnavailableError,
            WorkDomainError,
            WorkUnavailableError,
            EmployeeUnavailableError,
        ) as error:
            _raise_job_error(error)

    @strawberry.mutation
    async def provision_employee(self, info: Info, input: ProvisionEmployeeInput) -> AdminEmployee:
        subject = await _admin_subject(info)
        try:
            profile = await provision_admin_employee(
                subject,
                {
                    "idempotency_key": input.idempotency_key,
                    "username": input.username,
                    "email": input.email,
                    "display_name": input.display_name,
                    "role": input.role.value,
                    "active": input.active,
                    "temporary_password": input.temporary_password,
                },
            )
            return _admin_employee(profile)
        except (EmployeeDomainError, EmployeeUnavailableError) as error:
            _raise_admin_error(error)

    @strawberry.mutation
    async def update_employee_role(
        self, info: Info, employee_id: strawberry.ID, role: ApplicationRole
    ) -> AdminEmployee:
        subject = await _admin_subject(info)
        try:
            return _admin_employee(
                await update_admin_employee_role(subject, str(employee_id), role.value)
            )
        except (EmployeeDomainError, EmployeeUnavailableError) as error:
            _raise_admin_error(error)

    @strawberry.mutation
    async def set_employee_active(
        self, info: Info, employee_id: strawberry.ID, active: bool
    ) -> AdminEmployee:
        subject = await _admin_subject(info)
        try:
            return _admin_employee(
                await update_admin_employee_active(subject, str(employee_id), active)
            )
        except (EmployeeDomainError, EmployeeUnavailableError) as error:
            _raise_admin_error(error)

    @strawberry.mutation
    async def reconcile_employee(self, info: Info, employee_id: strawberry.ID) -> AdminEmployee:
        subject = await _admin_subject(info)
        try:
            return _admin_employee(await reconcile_admin_employee(subject, str(employee_id)))
        except (EmployeeDomainError, EmployeeUnavailableError) as error:
            _raise_admin_error(error)

    @strawberry.mutation
    async def create_project(self, info: Info, input: CreateProjectInput) -> Project:
        subject, actor = await _project_actor(info)
        if actor.role not in {"ADMIN", "MANAGER"}:
            raise GraphQLError(
                "Project creation is not permitted.", extensions={"code": "FORBIDDEN"}
            )
        try:
            return await _enriched_project(
                subject,
                await work_create_project(
                    actor,
                    {"key": input.key, "name": input.name, "description": input.description},
                ),
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.mutation
    async def update_project(
        self, info: Info, project_id: strawberry.ID, input: UpdateProjectInput
    ) -> Project:
        subject, actor = await _project_actor(info)
        try:
            return await _enriched_project(
                subject,
                await work_update_project(
                    actor,
                    str(project_id),
                    {
                        "name": input.name,
                        "description": input.description,
                        "expected_version": input.expected_version,
                    },
                ),
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.mutation
    async def set_project_status(
        self,
        info: Info,
        project_id: strawberry.ID,
        status: ProjectStatus,
        expected_version: int,
    ) -> Project:
        subject, actor = await _project_actor(info)
        try:
            return await _enriched_project(
                subject,
                await work_change_status(
                    actor,
                    str(project_id),
                    {"status": status.value, "expected_version": expected_version},
                ),
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.mutation
    async def add_project_member(
        self,
        info: Info,
        project_id: strawberry.ID,
        employee_id: strawberry.ID,
        role: ProjectRole,
    ) -> Project:
        subject, actor = await _project_actor(info)
        try:
            await validate_eligible_employee(subject, str(employee_id))
            return await _enriched_project(
                subject,
                await work_add_member(
                    actor,
                    str(project_id),
                    {"employee_id": str(employee_id), "role": role.value},
                ),
            )
        except (
            EmployeeDomainError,
            EmployeeUnavailableError,
            WorkDomainError,
            WorkUnavailableError,
        ) as error:
            _raise_project_error(error)

    @strawberry.mutation
    async def update_project_member_role(
        self,
        info: Info,
        project_id: strawberry.ID,
        employee_id: strawberry.ID,
        role: ProjectRole,
    ) -> Project:
        subject, actor = await _project_actor(info)
        try:
            return await _enriched_project(
                subject,
                await work_change_member_role(actor, str(project_id), str(employee_id), role.value),
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.mutation
    async def remove_project_member(
        self, info: Info, project_id: strawberry.ID, employee_id: strawberry.ID
    ) -> Project:
        subject, actor = await _project_actor(info)
        try:
            return await _enriched_project(
                subject,
                await work_remove_member(actor, str(project_id), str(employee_id)),
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.mutation
    async def create_task(
        self, info: Info, project_id: strawberry.ID, input: CreateTaskInput
    ) -> Task:
        subject, actor = await _project_actor(info)
        try:
            if input.assignee_employee_id:
                await validate_eligible_employee(subject, str(input.assignee_employee_id))
            value = await work_create_task(
                actor,
                str(project_id),
                {
                    "title": input.title,
                    "description": input.description,
                    "priority": input.priority.value,
                    "assignee_employee_id": (
                        str(input.assignee_employee_id) if input.assignee_employee_id else None
                    ),
                    "due_date": input.due_date.isoformat() if input.due_date else None,
                },
            )
            return await _enriched_task(subject, actor, value)
        except (
            EmployeeDomainError,
            EmployeeUnavailableError,
            WorkDomainError,
            WorkUnavailableError,
        ) as error:
            _raise_project_error(error)

    @strawberry.mutation
    async def update_task(
        self,
        info: Info,
        project_id: strawberry.ID,
        task_id: strawberry.ID,
        input: UpdateTaskInput,
    ) -> Task:
        subject, actor = await _project_actor(info)
        try:
            return await _enriched_task(
                subject,
                actor,
                await work_update_task(
                    actor,
                    str(project_id),
                    str(task_id),
                    {
                        "title": input.title,
                        "description": input.description,
                        "priority": input.priority.value,
                        "due_date": input.due_date.isoformat() if input.due_date else None,
                        "expected_version": input.expected_version,
                    },
                ),
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.mutation
    async def assign_task(
        self,
        info: Info,
        project_id: strawberry.ID,
        task_id: strawberry.ID,
        assignee_employee_id: strawberry.ID | None,
        expected_version: int,
    ) -> Task:
        subject, actor = await _project_actor(info)
        try:
            if assignee_employee_id:
                await validate_eligible_employee(subject, str(assignee_employee_id))
            return await _enriched_task(
                subject,
                actor,
                await work_assign_task(
                    actor,
                    str(project_id),
                    str(task_id),
                    {
                        "assignee_employee_id": (
                            str(assignee_employee_id) if assignee_employee_id else None
                        ),
                        "expected_version": expected_version,
                    },
                ),
            )
        except (
            EmployeeDomainError,
            EmployeeUnavailableError,
            WorkDomainError,
            WorkUnavailableError,
        ) as error:
            _raise_project_error(error)

    @strawberry.mutation
    async def change_task_status(
        self,
        info: Info,
        project_id: strawberry.ID,
        task_id: strawberry.ID,
        status: TaskStatus,
        expected_version: int,
    ) -> Task:
        subject, actor = await _project_actor(info)
        try:
            return await _enriched_task(
                subject,
                actor,
                await work_change_task_status(
                    actor,
                    str(project_id),
                    str(task_id),
                    {"status": status.value, "expected_version": expected_version},
                ),
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)

    @strawberry.mutation
    async def add_task_comment(
        self,
        info: Info,
        project_id: strawberry.ID,
        task_id: strawberry.ID,
        body: str,
    ) -> TaskComment:
        subject, actor = await _project_actor(info)
        try:
            value = await work_add_task_comment(actor, str(project_id), str(task_id), body)
            profiles = await resolve_employee_references(subject, [value.author_employee_id])
            return TaskComment(
                id=strawberry.ID(value.id),
                task_id=strawberry.ID(value.task_id),
                author_employee_id=strawberry.ID(value.author_employee_id),
                author_display_name=profiles[0].display_name if profiles else None,
                body=value.body,
                created_at=datetime.fromisoformat(value.created_at),
            )
        except (WorkDomainError, WorkUnavailableError, EmployeeUnavailableError) as error:
            _raise_project_error(error)


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[
        lambda: QueryDepthLimiter(max_depth=4),
        lambda: MaxAliasesLimiter(max_alias_count=10),
    ],
)
