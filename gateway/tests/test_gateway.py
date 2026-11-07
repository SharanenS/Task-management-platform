# ruff: noqa: E501
import asyncio
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from app.auth import AuthenticationError, Identity
from app.employee_client import (
    EligibleEmployee,
    EmployeeAdminPage,
    EmployeeAdminProfile,
    EmployeeDomainError,
    EmployeeForbiddenError,
    EmployeeProfile,
    EmployeeUnavailableError,
)
from app.job_client import (
    JobDashboardMetrics,
    JobDomainError,
    JobMetrics,
    JobPage,
    JobRecord,
    JobUnavailableError,
    PublicationPage,
    PublicationRecord,
)
from app.main import app
from app.notification_client import (
    NotificationDomainError,
    NotificationRecord,
    NotificationUnavailableError,
)
from app.notification_client import Page as NotificationPage
from app.schema import schema
from app.work_client import (
    WorkDashboardMetrics,
    WorkDashboardTaskItem,
    WorkDomainError,
    WorkMembership,
    WorkProject,
    WorkProjectMetrics,
    WorkProjectPage,
    WorkTask,
    WorkTaskMetrics,
    WorkTaskPage,
    WorkUnavailableError,
)
from app.workflow_client import Page as WorkflowPage
from app.workflow_client import Rule as WorkflowRuleRecord


def request(
    method: str,
    path: str,
    *,
    payload: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, path, json=payload, params=params, headers=headers)

    return asyncio.run(send())


def test_system_info_contract() -> None:
    response = request(
        "POST",
        "/graphql",
        payload={
            "query": """
      query SystemInfo { systemInfo { name version environment status } }
    """
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["systemInfo"] == {
        "name": "Enterprise Task Platform Gateway",
        "version": "0.1.0",
        "environment": "development",
        "status": "AVAILABLE",
    }
    assert response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("path,status", [("/health/live", "alive"), ("/health/ready", "ready")])
def test_health(path: str, status: str) -> None:
    assert request("GET", path).json() == {"status": status}


def test_schema_export_matches_runtime() -> None:
    assert Path("schema.graphql").read_text(encoding="utf-8") == schema.as_str() + "\n"


def test_invalid_queries_are_sanitized() -> None:
    result = request("POST", "/graphql", payload={"query": "{ employees { password } }"}).json()
    assert result["errors"] == [{"message": "Invalid GraphQL request."}]
    assert result.get("data") is None


def test_alias_abuse_is_rejected() -> None:
    fields = " ".join(f"a{i}: systemInfo {{ status }}" for i in range(11))
    result = request("POST", "/graphql", payload={"query": "{" + fields + "}"}).json()
    assert result["errors"]
    assert result.get("data") is None


def test_get_queries_are_disabled() -> None:
    response = request("GET", "/graphql", params={"query": "{ systemInfo { status } }"})
    assert response.status_code == 400


def test_me_requires_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(_: str | None) -> Identity:
        raise AuthenticationError

    monkeypatch.setattr("app.schema.token_validator.validate", reject)
    result = request("POST", "/graphql", payload={"query": "{ me { id } }"}).json()
    assert result["errors"] == [
        {
            "message": "Authentication is required.",
            "extensions": {"code": "UNAUTHENTICATED"},
        }
    ]


def test_workflow_directory_requires_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(_: str | None) -> Identity:
        raise AuthenticationError

    monkeypatch.setattr("app.schema.token_validator.validate", reject)
    result = request(
        "POST", "/graphql", payload={"query": "{ workflowRules { nodes { id } } }"}
    ).json()
    assert result["errors"] == [
        {"message": "Authentication is required.", "extensions": {"code": "UNAUTHENTICATED"}}
    ]


def test_workflow_directory_maps_typed_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.schema.token_validator.validate", lambda _: Identity(subject="subject-1")
    )
    actor = EmployeeProfile(
        id="11111111-1111-4111-8111-111111111111",
        display_name="Admin",
        email="admin@example.test",
        role="ADMIN",
    )

    async def employee(_: str) -> EmployeeProfile:
        return actor

    async def projects(*_: object, **__: object) -> WorkProjectPage:
        return WorkProjectPage([], None, False)

    async def workflows(*_: object, **__: object) -> WorkflowPage:
        return WorkflowPage(
            [
                WorkflowRuleRecord(
                    "22222222-2222-4222-8222-222222222222",
                    "33333333-3333-4333-8333-333333333333",
                    "Export done",
                    "TASK_COMPLETED",
                    "PROJECT_TASK_EXPORT",
                    True,
                    actor.id,
                    1,
                    "2026-10-28T00:00:00+00:00",
                    "2026-10-28T00:00:00+00:00",
                )
            ],
            None,
            False,
        )

    monkeypatch.setattr("app.schema.get_employee", employee)
    monkeypatch.setattr("app.schema.work_list_projects", projects)
    monkeypatch.setattr("app.schema.workflow_list_rules", workflows)
    result = request(
        "POST",
        "/graphql",
        payload={"query": "{ workflowRules { nodes { name triggerType actionType enabled } } }"},
        headers={"Authorization": "Bearer test"},
    ).json()
    assert result["data"]["workflowRules"]["nodes"] == [
        {
            "name": "Export done",
            "triggerType": "TASK_COMPLETED",
            "actionType": "PROJECT_TASK_EXPORT",
            "enabled": True,
        }
    ]


def test_me_returns_employee_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.schema.token_validator.validate", lambda _: Identity(subject="subject-1")
    )

    async def employee(_: str) -> EmployeeProfile:
        return EmployeeProfile(
            id="f45e9d94-f915-4b8b-ab9b-d34912ef582c",
            display_name="Avery Morgan",
            email="avery@example.test",
            role="MANAGER",
        )

    monkeypatch.setattr("app.schema.get_employee", employee)
    result = request(
        "POST",
        "/graphql",
        payload={"query": "{ me { id displayName email role } }"},
        headers={"Authorization": "Bearer test-token"},
    ).json()
    assert result["data"]["me"] == {
        "id": "f45e9d94-f915-4b8b-ab9b-d34912ef582c",
        "displayName": "Avery Morgan",
        "email": "avery@example.test",
        "role": "MANAGER",
    }


@pytest.mark.parametrize(
    ("error", "code", "message"),
    [
        (EmployeeForbiddenError(), "FORBIDDEN", "Access is not available for this account."),
        (
            EmployeeUnavailableError(),
            "SERVICE_UNAVAILABLE",
            "Employee profiles are temporarily unavailable.",
        ),
    ],
)
def test_me_sanitizes_employee_failures(
    monkeypatch: pytest.MonkeyPatch, error: Exception, code: str, message: str
) -> None:
    monkeypatch.setattr(
        "app.schema.token_validator.validate", lambda _: Identity(subject="subject-1")
    )

    async def employee(_: str) -> EmployeeProfile:
        raise error

    monkeypatch.setattr("app.schema.get_employee", employee)
    result = request(
        "POST",
        "/graphql",
        payload={"query": "{ me { id } }"},
        headers={"Authorization": "Bearer x"},
    ).json()
    assert result["errors"] == [{"message": message, "extensions": {"code": code}}]


@pytest.mark.parametrize("role", ["MEMBER", "MANAGER"])
def test_employee_directory_rejects_non_admin(monkeypatch: pytest.MonkeyPatch, role: str) -> None:
    monkeypatch.setattr(
        "app.schema.token_validator.validate", lambda _: Identity(subject="subject-1")
    )

    async def actor(_: str) -> EmployeeProfile:
        return EmployeeProfile(id="id", display_name="User", email="user@example.test", role=role)

    monkeypatch.setattr("app.schema.get_employee", actor)
    result = request(
        "POST",
        "/graphql",
        payload={"query": "{ employees(first: 10) { nodes { id } } }"},
        headers={"Authorization": "Bearer test"},
    ).json()
    assert result["errors"][0]["extensions"]["code"] == "FORBIDDEN"


def test_employee_directory_returns_typed_admin_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.schema.token_validator.validate", lambda _: Identity(subject="admin-subject")
    )

    async def actor(_: str) -> EmployeeProfile:
        return EmployeeProfile(
            id="admin-id", display_name="Admin", email="admin@example.test", role="ADMIN"
        )

    async def directory(*_: object, **__: object) -> EmployeeAdminPage:
        return EmployeeAdminPage(
            items=[
                EmployeeAdminProfile(
                    id="employee-id",
                    username="employee.user",
                    display_name="Employee User",
                    email="employee@example.test",
                    role="MEMBER",
                    active=True,
                    provisioning_status="COMPLETE",
                    created_at="2026-10-14T00:00:00+00:00",
                    updated_at="2026-10-14T00:00:00+00:00",
                    version=1,
                )
            ],
            next_cursor=None,
            has_next_page=False,
        )

    monkeypatch.setattr("app.schema.get_employee", actor)
    monkeypatch.setattr("app.schema.list_admin_employees", directory)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": """
            { employees(first: 10) {
              nodes { id username displayName email role active provisioningStatus }
              pageInfo { hasNextPage endCursor }
            } }
            """
        },
        headers={"Authorization": "Bearer test"},
    ).json()
    assert result["data"]["employees"]["nodes"][0]["username"] == "employee.user"
    assert result["data"]["employees"]["pageInfo"]["hasNextPage"] is False


def test_employee_directory_validates_page_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.schema.token_validator.validate", lambda _: Identity(subject="admin-subject")
    )

    async def actor(_: str) -> EmployeeProfile:
        return EmployeeProfile(
            id="admin-id", display_name="Admin", email="admin@example.test", role="ADMIN"
        )

    monkeypatch.setattr("app.schema.get_employee", actor)
    result = request(
        "POST",
        "/graphql",
        payload={"query": "{ employees(first: 51) { nodes { id } } }"},
        headers={"Authorization": "Bearer test"},
    ).json()
    assert result["errors"]


def admin_profile() -> EmployeeAdminProfile:
    return EmployeeAdminProfile(
        id="employee-id",
        username="employee.user",
        display_name="Employee User",
        email="employee@example.test",
        role="MEMBER",
        active=True,
        provisioning_status="COMPLETE",
        created_at="2026-10-14T00:00:00+00:00",
        updated_at="2026-10-14T00:00:00+00:00",
        version=1,
    )


def allow_admin(monkeypatch: pytest.MonkeyPatch, role: str = "ADMIN") -> None:
    monkeypatch.setattr(
        "app.schema.token_validator.validate", lambda _: Identity(subject="actor-subject")
    )

    async def actor(_: str) -> EmployeeProfile:
        return EmployeeProfile(
            id="actor", display_name="Actor", email="actor@example.test", role=role
        )

    monkeypatch.setattr("app.schema.get_employee", actor)


def work_project() -> WorkProject:
    return WorkProject(
        id="project-id",
        key="OPS",
        name="Operations",
        description=None,
        status="DRAFT",
        creator_employee_id="actor",
        version=1,
        created_at="2026-10-14T00:00:00+00:00",
        updated_at="2026-10-14T00:00:00+00:00",
        memberships=[],
    )


def work_task() -> WorkTask:
    return WorkTask(
        id="task-id",
        project_id="project-id",
        number=1,
        title="Review changes",
        description=None,
        status="TODO",
        priority="HIGH",
        assignee_employee_id="employee-1",
        creator_employee_id="actor",
        due_date=None,
        version=1,
        created_at="2026-10-15T00:00:00+00:00",
        updated_at="2026-10-15T00:00:00+00:00",
    )


@pytest.mark.parametrize(
    "operation",
    [
        '{ projectTasks(projectId: "project-id", first: 10, unassigned: false) { nodes { id } } }',
        '{ projectTaskBoard(projectId: "project-id") { lanes { status } } }',
        '{ task(projectId: "project-id", taskId: "task-id") { id } }',
        '{ taskComments(projectId: "project-id", taskId: "task-id") { nodes { id } } }',
        '{ taskActivity(projectId: "project-id", taskId: "task-id") { nodes { id } } }',
        'mutation { createTask(projectId: "project-id", input: {title: "Task"}) { id } }',
        'mutation { updateTask(projectId: "project-id", taskId: "task-id", input: {title: "Task", description: null, priority: HIGH, dueDate: null, expectedVersion: 1}) { id } }',
        'mutation { assignTask(projectId: "project-id", taskId: "task-id", assigneeEmployeeId: null, expectedVersion: 1) { id } }',
        'mutation { changeTaskStatus(projectId: "project-id", taskId: "task-id", status: IN_PROGRESS, expectedVersion: 1) { id } }',
        'mutation { addTaskComment(projectId: "project-id", taskId: "task-id", body: "Comment") { id } }',
    ],
)
def test_every_task_operation_rejects_unauthenticated(operation: str) -> None:
    result = request("POST", "/graphql", payload={"query": operation}).json()
    assert result["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"


def test_task_list_batches_assignee_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_admin(monkeypatch, "MEMBER")

    async def project(*_: object, **__: object) -> WorkProject:
        return work_project()

    async def tasks(*_: object, **__: object) -> WorkTaskPage:
        second = WorkTask(**{**work_task().__dict__, "id": "task-2"})
        return WorkTaskPage([work_task(), second], None, False)

    calls: list[list[str]] = []

    async def resolve(_: str, employee_ids: list[str]) -> list[EligibleEmployee]:
        calls.append(employee_ids)
        return [EligibleEmployee("employee-1", "Employee One", "one@example.test")]

    monkeypatch.setattr("app.schema.work_get_project", project)
    monkeypatch.setattr("app.schema.work_list_tasks", tasks)
    monkeypatch.setattr("app.schema.resolve_employee_references", resolve)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": '{ projectTasks(projectId: "project-id", first: 10, unassigned: false) { nodes { reference assigneeDisplayName } } }'
        },
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["data"]["projectTasks"]["nodes"][0] == {
        "reference": "OPS-1",
        "assigneeDisplayName": "Employee One",
    }
    assert calls == [["employee-1"]]


def test_create_task_validates_assignee_before_work(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_admin(monkeypatch, "MANAGER")
    sequence: list[str] = []

    async def validate(*_: object) -> EligibleEmployee:
        sequence.append("employee")
        return EligibleEmployee("employee-1", "Employee", "employee@example.test")

    async def create(*_: object, **__: object) -> WorkTask:
        sequence.append("work")
        return work_task()

    async def project(*_: object, **__: object) -> WorkProject:
        return work_project()

    async def resolve(*_: object, **__: object) -> list[EligibleEmployee]:
        return []

    monkeypatch.setattr("app.schema.validate_eligible_employee", validate)
    monkeypatch.setattr("app.schema.work_create_task", create)
    monkeypatch.setattr("app.schema.work_get_project", project)
    monkeypatch.setattr("app.schema.resolve_employee_references", resolve)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": 'mutation { createTask(projectId: "project-id", input: {title: "Task", assigneeEmployeeId: "employee-1"}) { id } }'
        },
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result.get("errors") is None
    assert sequence == ["employee", "work"]


def test_current_contributor_profile_can_create_unassigned_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow_admin(monkeypatch, "MEMBER")
    captured: list[tuple[str, str, dict[str, object]]] = []

    async def create(actor: EmployeeProfile, project_id: str, data: dict[str, object]) -> WorkTask:
        captured.append((actor.id, project_id, data))
        return WorkTask(**{**work_task().__dict__, "creator_employee_id": actor.id})

    async def project(*_: object, **__: object) -> WorkProject:
        return work_project()

    async def resolve(*_: object, **__: object) -> list[EligibleEmployee]:
        return []

    monkeypatch.setattr("app.schema.work_create_task", create)
    monkeypatch.setattr("app.schema.work_get_project", project)
    monkeypatch.setattr("app.schema.resolve_employee_references", resolve)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": 'mutation { createTask(projectId: "project-id", input: {title: "Contributor task", dueDate: "2026-12-01"}) { creatorEmployeeId dueDate } }'
        },
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result.get("errors") is None
    assert result["data"]["createTask"] == {
        "creatorEmployeeId": "actor",
        "dueDate": None,
    }
    assert captured == [
        (
            "actor",
            "project-id",
            {
                "title": "Contributor task",
                "description": None,
                "priority": "MEDIUM",
                "assignee_employee_id": None,
                "due_date": "2026-12-01",
            },
        )
    ]


@pytest.mark.parametrize("profile_error", [EmployeeForbiddenError(), EmployeeUnavailableError()])
def test_task_creation_requires_current_available_employee_profile(
    monkeypatch: pytest.MonkeyPatch, profile_error: Exception
) -> None:
    monkeypatch.setattr(
        "app.schema.token_validator.validate", lambda _: Identity(subject="actor-subject")
    )

    async def actor(_: str) -> EmployeeProfile:
        raise profile_error

    called = False

    async def create(*_: object, **__: object) -> WorkTask:
        nonlocal called
        called = True
        return work_task()

    monkeypatch.setattr("app.schema.get_employee", actor)
    monkeypatch.setattr("app.schema.work_create_task", create)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": 'mutation { createTask(projectId: "project-id", input: {title: "Task"}) { id } }'
        },
        headers={"Authorization": "Bearer token"},
    ).json()
    expected = (
        "FORBIDDEN" if isinstance(profile_error, EmployeeForbiddenError) else "SERVICE_UNAVAILABLE"
    )
    assert result["errors"][0]["extensions"]["code"] == expected
    assert called is False


def test_activity_history_has_no_public_edit_or_delete_mutation() -> None:
    exported = schema.as_str()
    assert "updateTaskActivity" not in exported
    assert "deleteTaskActivity" not in exported


def test_task_dependency_failure_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_admin(monkeypatch)

    async def project(*_: object, **__: object) -> WorkProject:
        raise WorkUnavailableError

    monkeypatch.setattr("app.schema.work_get_project", project)
    result = request(
        "POST",
        "/graphql",
        payload={"query": '{ task(projectId: "project-id", taskId: "task-id") { id } }'},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"] == [
        {
            "message": "Project management is temporarily unavailable.",
            "extensions": {"code": "SERVICE_UNAVAILABLE"},
        }
    ]


def test_projects_reload_current_profile_and_return_typed_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow_admin(monkeypatch, "MEMBER")

    async def directory(*_: object, **__: object) -> WorkProjectPage:
        return WorkProjectPage([work_project()], None, False)

    monkeypatch.setattr("app.schema.work_list_projects", directory)
    result = request(
        "POST",
        "/graphql",
        payload={"query": "{ projects(first: 10) { nodes { id key name status } } }"},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["data"]["projects"]["nodes"][0]["key"] == "OPS"


def test_member_cannot_forge_project_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_admin(monkeypatch, "MEMBER")
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": 'mutation { createProject(input: {key: "OPS", name: "Operations"}) { id } }'
        },
        headers={"Authorization": "Bearer forged-request"},
    ).json()
    assert result["errors"][0]["extensions"]["code"] == "FORBIDDEN"


def test_project_domain_errors_are_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_admin(monkeypatch)

    async def project(*_: object, **__: object) -> WorkProject:
        raise WorkDomainError("VERSION_CONFLICT", "The project changed; reload and retry.")

    monkeypatch.setattr("app.schema.work_get_project", project)
    result = request(
        "POST",
        "/graphql",
        payload={"query": '{ project(id: "project-id") { id } }'},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"] == [
        {
            "message": "The project changed; reload and retry.",
            "extensions": {"code": "VERSION_CONFLICT"},
        }
    ]


def test_assigned_member_removal_error_is_mapped_without_internal_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow_admin(monkeypatch, "MANAGER")

    async def remove(*_: object, **__: object) -> WorkProject:
        raise WorkDomainError(
            "MEMBER_HAS_ASSIGNED_TASKS",
            "PRIVATE response from http://work.internal with database detail",
        )

    monkeypatch.setattr("app.schema.work_remove_member", remove)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": 'mutation { removeProjectMember(projectId: "project-id", employeeId: "employee-id") { id } }'
        },
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"] == [
        {
            "message": "Reassign the employee's tasks before removing project membership.",
            "extensions": {"code": "MEMBER_HAS_ASSIGNED_TASKS"},
        }
    ]


def job_record() -> JobRecord:
    return JobRecord(
        id="job-id",
        job_type="PROJECT_TASK_EXPORT",
        status="SUBMITTED",
        submitter_employee_id="actor",
        related_project_id="project-id",
        payload={"projectId": "project-id", "format": "CSV", "includeCompleted": True},
        result_summary=None,
        result_content=None,
        result_content_type=None,
        result_checksum=None,
        result_row_count=None,
        result_truncated=None,
        failure_classification=None,
        completed_at=None,
        version=1,
        created_at="2026-10-16T00:00:00+00:00",
        updated_at="2026-10-16T00:00:00+00:00",
    )


def publication_record(status: str = "FAILED") -> PublicationRecord:
    return PublicationRecord(
        id="event-id",
        job_id="job-id",
        status=status,
        attempt_count=2,
        available_at="2026-10-20T00:00:05+00:00",
        lease_expires_at=("2026-10-20T00:00:10+00:00" if status == "IN_FLIGHT" else None),
        published_at=("2026-10-20T00:00:04+00:00" if status == "PUBLISHED" else None),
        last_failure_classification=("CONNECTION_FAILED" if status == "FAILED" else None),
        reconciliation_required=status == "RECONCILIATION_REQUIRED",
    )


@pytest.mark.parametrize("role", ["MEMBER", "MANAGER"])
def test_publication_diagnostics_reject_non_admin_before_job_call(
    monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    allow_admin(monkeypatch, role)
    called = False

    async def directory(*_: object, **__: object) -> PublicationPage:
        nonlocal called
        called = True
        return PublicationPage([], None, False)

    monkeypatch.setattr("app.schema.job_list_publications", directory)
    result = request(
        "POST",
        "/graphql",
        payload={"query": "{ jobPublications { nodes { id } } }"},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"][0]["extensions"]["code"] == "FORBIDDEN"
    assert not called


@pytest.mark.parametrize(
    "status", ["PENDING", "IN_FLIGHT", "FAILED", "PUBLISHED", "RECONCILIATION_REQUIRED"]
)
def test_admin_publication_diagnostics_are_typed_and_sanitized(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    allow_admin(monkeypatch)

    async def directory(*_: object, **__: object) -> PublicationPage:
        return PublicationPage([publication_record(status)], "opaque-next", True)

    monkeypatch.setattr("app.schema.job_list_publications", directory)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": "{ jobPublications(first: 10) { nodes { id status attemptCount nextRetryAt leaseExpiresAt publishedAt lastFailureClassification reconciliationRequired } pageInfo { hasNextPage endCursor } } }"
        },
        headers={"Authorization": "Bearer token"},
    ).json()
    serialized = str(result)
    assert result["data"]["jobPublications"]["nodes"][0]["status"] == status
    assert result["data"]["jobPublications"]["pageInfo"]["endCursor"] == "opaque-next"
    assert "leaseToken" not in serialized and "amqp://" not in serialized


def test_owned_job_exposes_publication_without_lease_token(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_admin(monkeypatch, "MEMBER")
    value = replace(
        job_record(),
        publication={
            "id": "event-id",
            "status": "FAILED",
            "attempt_count": 2,
            "available_at": "2026-10-20T00:00:05+00:00",
            "lease_expires_at": None,
            "published_at": None,
            "last_failure_classification": "CONNECTION_FAILED",
            "reconciliation_required": False,
            "lease_token": "must-never-appear",
        },
    )

    async def current(*_: object, **__: object) -> JobRecord:
        return value

    monkeypatch.setattr("app.schema.job_get_job", current)
    monkeypatch.setattr("app.schema.job_list_attempts", lambda *_: asyncio.sleep(0, result=[]))
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": '{ job(id: "job-id") { publication { status attemptCount nextRetryAt } } }'
        },
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["data"]["job"]["publication"]["status"] == "FAILED"
    assert "must-never-appear" not in str(result)


@pytest.mark.parametrize("role", ["MEMBER", "MANAGER"])
def test_admin_retry_rejects_non_admin_before_job_call(
    monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    allow_admin(monkeypatch, role)
    called = False

    async def retry(*_: object, **__: object) -> JobRecord:
        nonlocal called
        called = True
        return job_record()

    monkeypatch.setattr("app.schema.job_retry_job", retry)
    result = request(
        "POST",
        "/graphql",
        payload={"query": 'mutation { retryJob(jobId: "job-id", expectedVersion: 1) { id } }'},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"][0]["extensions"]["code"] == "FORBIDDEN"
    assert not called


def test_admin_retry_returns_typed_recovery_state(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_admin(monkeypatch)

    async def retry(*_: object, **__: object) -> JobRecord:
        return replace(
            job_record(),
            status="QUEUED",
            version=2,
            execution_generation=2,
            retry_exhausted=False,
            manual_retry_count=1,
        )

    monkeypatch.setattr("app.schema.job_retry_job", retry)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": 'mutation { retryJob(jobId: "job-id", expectedVersion: 1) { status version executionGeneration retryExhausted manualRetryCount } }'
        },
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["data"]["retryJob"] == {
        "status": "QUEUED",
        "version": 2,
        "executionGeneration": 2,
        "retryExhausted": False,
        "manualRetryCount": 1,
    }


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("JOB_NOT_RETRYABLE", "The job is not eligible for administrative retry."),
        ("JOB_RETRY_CONFLICT", "The retry request conflicted. Refresh and try again."),
    ],
)
def test_admin_retry_conflicts_are_sanitized(
    monkeypatch: pytest.MonkeyPatch, code: str, message: str
) -> None:
    allow_admin(monkeypatch)

    async def retry(*_: object, **__: object) -> JobRecord:
        raise JobDomainError(code, "internal detail must not appear")

    monkeypatch.setattr("app.schema.job_retry_job", retry)
    result = request(
        "POST",
        "/graphql",
        payload={"query": 'mutation { retryJob(jobId: "job-id", expectedVersion: 1) { id } }'},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"] == [{"message": message, "extensions": {"code": code}}]
    assert "internal detail" not in str(result)


@pytest.mark.parametrize("role", ["MEMBER", "MANAGER", "ADMIN"])
def test_jobs_reload_current_profile_and_return_typed_owned_data(
    monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    allow_admin(monkeypatch, role)

    async def directory(*_: object, **__: object) -> JobPage:
        return JobPage([job_record()], None, False)

    monkeypatch.setattr("app.schema.job_list_jobs", directory)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": "{ jobs(first: 10) { nodes { id jobType status payload { projectId format includeCompleted } attempts { id } } } }"
        },
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["data"]["jobs"]["nodes"] == [
        {
            "id": "job-id",
            "jobType": "PROJECT_TASK_EXPORT",
            "status": "SUBMITTED",
            "payload": {"projectId": "project-id", "format": "CSV", "includeCompleted": True},
            "attempts": [],
        }
    ]


def test_missing_profile_denies_job_access_before_job_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.schema.token_validator.validate", lambda _: Identity(subject="missing-subject")
    )

    async def missing(_: str) -> EmployeeProfile:
        raise EmployeeForbiddenError

    called = False

    async def directory(*_: object, **__: object) -> JobPage:
        nonlocal called
        called = True
        raise AssertionError

    monkeypatch.setattr("app.schema.get_employee", missing)
    monkeypatch.setattr("app.schema.job_list_jobs", directory)
    result = request(
        "POST",
        "/graphql",
        payload={"query": "{ jobs { nodes { id } } }"},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"][0]["extensions"]["code"] == "FORBIDDEN"
    assert called is False


def test_submit_job_validates_project_before_job_service(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_admin(monkeypatch, "MEMBER")
    sequence: list[str] = []

    async def project(*_: object, **__: object) -> WorkProject:
        sequence.append("work")
        return work_project()

    async def submit(*_: object, **__: object) -> JobRecord:
        sequence.append("job")
        return job_record()

    monkeypatch.setattr("app.schema.work_get_project", project)
    monkeypatch.setattr("app.schema.job_submit_job", submit)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": 'mutation { submitProjectTaskExport(input: {projectId: "project-id", includeCompleted: true, idempotencyKey: "phase6-gateway-key-0001"}) { id status attempts { id } } }'
        },
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["data"]["submitProjectTaskExport"] == {
        "id": "job-id",
        "status": "SUBMITTED",
        "attempts": [],
    }
    assert sequence == ["work", "job"]


def test_dispatch_job_revalidates_project_before_publish(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_admin(monkeypatch, "MEMBER")
    sequence: list[str] = []

    async def current(*_: object, **__: object) -> JobRecord:
        sequence.append("job-read")
        return job_record()

    async def project(*_: object, **__: object) -> WorkProject:
        sequence.append("work")
        return work_project()

    async def dispatch(*_: object, **__: object) -> JobRecord:
        sequence.append("dispatch")
        value = job_record()
        return replace(value, status="QUEUED", version=2)

    monkeypatch.setattr("app.schema.job_get_job", current)
    monkeypatch.setattr("app.schema.work_get_project", project)
    monkeypatch.setattr("app.schema.job_dispatch_job", dispatch)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": 'mutation { dispatchJob(jobId: "job-id", expectedVersion: 1) { id status version } }'
        },
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["data"]["dispatchJob"] == {"id": "job-id", "status": "QUEUED", "version": 2}
    assert sequence == ["job-read", "work", "dispatch"]


@pytest.mark.parametrize(
    ("domain_code", "message"),
    [
        ("VERSION_CONFLICT", "The job changed before it could be dispatched."),
        ("JOB_NOT_DISPATCHABLE", "The job cannot be dispatched in its current state."),
        ("BROKER_UNAVAILABLE", "Job dispatch is temporarily unavailable."),
    ],
)
def test_dispatch_job_errors_are_fixed(
    monkeypatch: pytest.MonkeyPatch, domain_code: str, message: str
) -> None:
    allow_admin(monkeypatch)

    async def current(*_: object, **__: object) -> JobRecord:
        return job_record()

    async def project(*_: object, **__: object) -> WorkProject:
        return work_project()

    async def dispatch(*_: object, **__: object) -> JobRecord:
        raise JobDomainError(domain_code, "sensitive upstream detail")

    monkeypatch.setattr("app.schema.job_get_job", current)
    monkeypatch.setattr("app.schema.work_get_project", project)
    monkeypatch.setattr("app.schema.job_dispatch_job", dispatch)
    result = request(
        "POST",
        "/graphql",
        payload={"query": 'mutation { dispatchJob(jobId: "job-id", expectedVersion: 1) { id } }'},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"] == [{"message": message, "extensions": {"code": domain_code}}]


@pytest.mark.parametrize(
    ("error", "code", "message"),
    [
        (
            JobDomainError("IDEMPOTENCY_CONFLICT", "private database detail"),
            "IDEMPOTENCY_CONFLICT",
            "The idempotency key is already in use.",
        ),
        (
            JobUnavailableError(),
            "SERVICE_UNAVAILABLE",
            "Job management is temporarily unavailable.",
        ),
    ],
)
def test_job_errors_are_fixed_and_sanitized(
    monkeypatch: pytest.MonkeyPatch, error: Exception, code: str, message: str
) -> None:
    allow_admin(monkeypatch)

    async def directory(*_: object, **__: object) -> JobPage:
        raise error

    monkeypatch.setattr("app.schema.job_list_jobs", directory)
    result = request(
        "POST",
        "/graphql",
        payload={"query": "{ jobs { nodes { id } } }"},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"] == [{"message": message, "extensions": {"code": code}}]
    assert "private database detail" not in str(result)
    serialized = str(result)
    assert "http://" not in serialized
    assert "private" not in serialized.lower()
    assert "database" not in serialized.lower()
    assert "traceback" not in serialized.lower()


@pytest.mark.parametrize(
    "operation",
    [
        "{ projects(first: 10) { nodes { id } } }",
        '{ project(id: "project-id") { id } }',
        'mutation { createProject(input: {key: "OPS", name: "Operations"}) { id } }',
        'mutation { updateProject(projectId: "project-id", input: {name: "Updated", description: null, expectedVersion: 1}) { id } }',
        'mutation { setProjectStatus(projectId: "project-id", status: ACTIVE, expectedVersion: 1) { id } }',
        'mutation { addProjectMember(projectId: "project-id", employeeId: "employee-id", role: CONTRIBUTOR) { id } }',
        'mutation { updateProjectMemberRole(projectId: "project-id", employeeId: "employee-id", role: PROJECT_MANAGER) { id } }',
        'mutation { removeProjectMember(projectId: "project-id", employeeId: "employee-id") { id } }',
        "{ eligibleProjectMembers(first: 10) { nodes { id } } }",
    ],
)
def test_every_project_operation_rejects_unauthenticated(operation: str) -> None:
    result = request("POST", "/graphql", payload={"query": operation}).json()
    assert result["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"


def test_inactive_profile_rejects_project_access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.schema.token_validator.validate", lambda _: Identity(subject="inactive-subject")
    )

    async def inactive(_: str) -> EmployeeProfile:
        raise EmployeeForbiddenError

    monkeypatch.setattr("app.schema.get_employee", inactive)
    result = request(
        "POST",
        "/graphql",
        payload={"query": "{ projects(first: 10) { nodes { id } } }"},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"][0]["extensions"]["code"] == "FORBIDDEN"


@pytest.mark.parametrize("role", ["ADMIN", "MANAGER"])
def test_admin_and_manager_create_project(monkeypatch: pytest.MonkeyPatch, role: str) -> None:
    allow_admin(monkeypatch, role)

    async def create(*_: object, **__: object) -> WorkProject:
        return work_project()

    monkeypatch.setattr("app.schema.work_create_project", create)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": 'mutation { createProject(input: {key: "OPS", name: "Operations"}) { key status version } }'
        },
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["data"]["createProject"] == {
        "key": "OPS",
        "status": "DRAFT",
        "version": 1,
    }


def test_project_members_are_resolved_in_one_bounded_employee_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow_admin(monkeypatch)
    first = work_project()
    first.memberships.extend(
        [
            WorkMembership("membership-1", "employee-1", "PROJECT_MANAGER", first.created_at),
            WorkMembership("membership-2", "employee-2", "CONTRIBUTOR", first.created_at),
        ]
    )
    second = WorkProject(**{**first.__dict__, "id": "project-2", "memberships": first.memberships})

    async def directory(*_: object, **__: object) -> WorkProjectPage:
        return WorkProjectPage([first, second], None, False)

    calls: list[list[str]] = []

    async def resolve(_: str, employee_ids: list[str]) -> list[EligibleEmployee]:
        calls.append(employee_ids)
        return [EligibleEmployee("employee-1", "Active Manager", "manager@example.test")]

    monkeypatch.setattr("app.schema.work_list_projects", directory)
    monkeypatch.setattr("app.schema.resolve_employee_references", resolve)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": "{ projects(first: 10) { nodes { memberships { employeeId displayName email } } } }"
        },
        headers={"Authorization": "Bearer token"},
    ).json()
    assert calls == [["employee-1", "employee-2"]]
    memberships = result["data"]["projects"]["nodes"][0]["memberships"]
    assert memberships[0]["displayName"] == "Active Manager"
    assert memberships[1]["displayName"] is None
    assert memberships[1]["email"] is None


@pytest.mark.parametrize(
    ("operation", "client_name"),
    [
        (
            'mutation { updateProject(projectId: "project-id", input: {name: "Updated", description: null, expectedVersion: 1}) { id } }',
            "work_update_project",
        ),
        (
            'mutation { setProjectStatus(projectId: "project-id", status: ACTIVE, expectedVersion: 1) { id } }',
            "work_change_status",
        ),
        (
            'mutation { updateProjectMemberRole(projectId: "project-id", employeeId: "employee-id", role: PROJECT_MANAGER) { id } }',
            "work_change_member_role",
        ),
        (
            'mutation { removeProjectMember(projectId: "project-id", employeeId: "employee-id") { id } }',
            "work_remove_member",
        ),
    ],
)
def test_project_mutations_return_typed_payloads(
    monkeypatch: pytest.MonkeyPatch, operation: str, client_name: str
) -> None:
    allow_admin(monkeypatch)

    async def client(*_: object, **__: object) -> WorkProject:
        return work_project()

    monkeypatch.setattr(f"app.schema.{client_name}", client)
    result = request(
        "POST",
        "/graphql",
        payload={"query": operation},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result.get("errors") is None
    assert next(iter(result["data"].values()))["id"] == "project-id"


def test_add_member_validates_employee_before_work_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow_admin(monkeypatch, "MANAGER")
    sequence: list[str] = []

    async def validate(*_: object) -> EligibleEmployee:
        sequence.append("employee")
        return EligibleEmployee("employee-id", "Employee", "employee@example.test")

    async def add(*_: object, **__: object) -> WorkProject:
        sequence.append("work")
        return work_project()

    monkeypatch.setattr("app.schema.validate_eligible_employee", validate)
    monkeypatch.setattr("app.schema.work_add_member", add)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": 'mutation { addProjectMember(projectId: "project-id", employeeId: "employee-id", role: CONTRIBUTOR) { id } }'
        },
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result.get("errors") is None
    assert sequence == ["employee", "work"]


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (WorkUnavailableError(), "Project management is temporarily unavailable."),
        (EmployeeUnavailableError(), "Project management is temporarily unavailable."),
    ],
)
def test_project_dependency_failures_are_sanitized(
    monkeypatch: pytest.MonkeyPatch, error: Exception, message: str
) -> None:
    allow_admin(monkeypatch)

    async def directory(*_: object, **__: object) -> WorkProjectPage:
        raise error

    monkeypatch.setattr("app.schema.work_list_projects", directory)
    result = request(
        "POST",
        "/graphql",
        payload={"query": "{ projects(first: 10) { nodes { id } } }"},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"] == [{"message": message, "extensions": {"code": "SERVICE_UNAVAILABLE"}}]
    serialized = str(result).lower()
    assert "http://work" not in serialized
    assert "connection" not in serialized


@pytest.mark.parametrize(
    "query",
    [
        '{ employee(id: "employee-id") { id } }',
        'mutation { provisionEmployee(input: {idempotencyKey: "request-1234", username: "user.name", email: "user@example.test", displayName: "User Name", role: MEMBER, active: true, temporaryPassword: "temporary-password"}) { id } }',
        'mutation { updateEmployeeRole(employeeId: "employee-id", role: MANAGER) { id } }',
        'mutation { setEmployeeActive(employeeId: "employee-id", active: false) { id } }',
        'mutation { reconcileEmployee(employeeId: "employee-id") { id } }',
    ],
)
def test_every_admin_operation_rejects_unauthenticated(query: str) -> None:
    result = request("POST", "/graphql", payload={"query": query}).json()
    assert result["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize("role", ["MEMBER", "MANAGER"])
def test_direct_graphql_mutation_rejects_non_admin(
    monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    allow_admin(monkeypatch, role)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": 'mutation { setEmployeeActive(employeeId: "employee-id", active: false) { id } }'
        },
        headers={"Authorization": "Bearer forged-browser-request"},
    ).json()
    assert result["errors"][0]["extensions"]["code"] == "FORBIDDEN"


@pytest.mark.parametrize(
    ("operation", "client_name"),
    [
        (
            '{ employee(id: "employee-id") { id username role active provisioningStatus } }',
            "get_admin_employee",
        ),
        (
            'mutation { provisionEmployee(input: {idempotencyKey: "request-1234", username: "user.name", email: "user@example.test", displayName: "User Name", role: MEMBER, active: true, temporaryPassword: "temporary-password"}) { id } }',
            "provision_admin_employee",
        ),
        (
            'mutation { updateEmployeeRole(employeeId: "employee-id", role: MANAGER) { id } }',
            "update_admin_employee_role",
        ),
        (
            'mutation { setEmployeeActive(employeeId: "employee-id", active: false) { id } }',
            "update_admin_employee_active",
        ),
        (
            'mutation { reconcileEmployee(employeeId: "employee-id") { id } }',
            "reconcile_admin_employee",
        ),
    ],
)
def test_admin_employee_operations_return_typed_payloads(
    monkeypatch: pytest.MonkeyPatch, operation: str, client_name: str
) -> None:
    allow_admin(monkeypatch)

    async def client(*args: object, **kwargs: object) -> EmployeeAdminProfile:
        return admin_profile()

    monkeypatch.setattr(f"app.schema.{client_name}", client)
    result = request(
        "POST", "/graphql", payload={"query": operation}, headers={"Authorization": "Bearer token"}
    ).json()
    assert result.get("errors") is None
    assert next(iter(result["data"].values()))["id"] == "employee-id"


@pytest.mark.parametrize(
    ("error", "code", "message"),
    [
        (
            EmployeeDomainError("INVALID_INPUT", "The pagination cursor is invalid."),
            "INVALID_INPUT",
            "The pagination cursor is invalid.",
        ),
        (
            EmployeeUnavailableError(),
            "SERVICE_UNAVAILABLE",
            "Employee administration is temporarily unavailable.",
        ),
    ],
)
def test_admin_errors_are_sanitized(
    monkeypatch: pytest.MonkeyPatch, error: Exception, code: str, message: str
) -> None:
    allow_admin(monkeypatch)

    async def client(*args: object, **kwargs: object) -> EmployeeAdminProfile:
        raise error

    monkeypatch.setattr("app.schema.get_admin_employee", client)
    result = request(
        "POST",
        "/graphql",
        payload={"query": '{ employee(id: "employee-id") { id } }'},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"] == [{"message": message, "extensions": {"code": code}}]
    assert "http://employee" not in str(result)


def test_notifications_require_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.schema.token_validator.validate",
        lambda _: (_ for _ in ()).throw(AuthenticationError()),
    )
    result = request(
        "POST", "/graphql", payload={"query": "{ notifications { nodes { id } } }"}
    ).json()
    assert result["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"


def test_notification_contract_is_recipient_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_admin(monkeypatch)
    item = NotificationRecord(
        "11111111-1111-4111-8111-111111111112",
        "11111111-1111-4111-8111-111111111111",
        "TASK_ASSIGNED",
        "Task assigned",
        "A task was assigned to you.",
        "11111111-1111-4111-8111-111111111113",
        "11111111-1111-4111-8111-111111111114",
        "11111111-1111-4111-8111-111111111115",
        None,
        None,
        "2026-10-29T00:00:00+00:00",
    )

    async def notifications(*args: object, **kwargs: object) -> NotificationPage:
        actor = args[0]
        assert isinstance(actor, EmployeeProfile)
        assert actor.id == "actor"
        return NotificationPage([item], None, False)

    monkeypatch.setattr("app.schema.notification_list", notifications)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": "{ notifications { nodes { id notificationType title message readAt } } }"
        },
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result.get("errors") is None
    assert result["data"]["notifications"]["nodes"][0]["notificationType"] == "TASK_ASSIGNED"
    assert "recipientEmployeeId" not in str(result)


def test_foreign_notification_is_concealed(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_admin(monkeypatch)

    async def denied(*args: object, **kwargs: object) -> NotificationRecord:
        raise NotificationDomainError("NOT_FOUND", "internal foreign row")

    monkeypatch.setattr("app.schema.notification_mark_read", denied)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": 'mutation { markNotificationRead(id: "11111111-1111-4111-8111-111111111112") { id } }'
        },
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"] == [
        {"message": "The notification was not found.", "extensions": {"code": "NOT_FOUND"}}
    ]
    assert "foreign" not in str(result)


def test_all_notification_operations_are_scoped_to_current_employee(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow_admin(monkeypatch, "MEMBER")
    calls: list[tuple[str, str]] = []
    item = NotificationRecord(
        "11111111-1111-4111-8111-111111111112",
        "actor",
        "TASK_ASSIGNED",
        "Task assigned",
        "A task was assigned to you.",
        "11111111-1111-4111-8111-111111111113",
        None,
        None,
        None,
        None,
        "2026-10-29T00:00:00+00:00",
    )

    async def listing(actor: EmployeeProfile, **_: object) -> NotificationPage:
        calls.append(("list", actor.id))
        return NotificationPage([item], None, False)

    async def count(actor: EmployeeProfile) -> int:
        calls.append(("count", actor.id))
        return 1

    async def mark(actor: EmployeeProfile, _: str) -> NotificationRecord:
        calls.append(("mark", actor.id))
        return item

    async def mark_all(actor: EmployeeProfile) -> int:
        calls.append(("all", actor.id))
        return 1

    monkeypatch.setattr("app.schema.notification_list", listing)
    monkeypatch.setattr("app.schema.notification_unread_count", count)
    monkeypatch.setattr("app.schema.notification_mark_read", mark)
    monkeypatch.setattr("app.schema.notification_mark_all", mark_all)
    for query in (
        "{ notifications { nodes { id } } unreadNotificationCount }",
        'mutation { markNotificationRead(id: "11111111-1111-4111-8111-111111111112") { id } }',
        "mutation { markAllNotificationsRead { updatedCount } }",
    ):
        result = request(
            "POST", "/graphql", payload={"query": query}, headers={"Authorization": "Bearer token"}
        ).json()
        assert result.get("errors") is None
    assert calls == [("list", "actor"), ("count", "actor"), ("mark", "actor"), ("all", "actor")]


@pytest.mark.parametrize("profile_state", ["missing", "inactive"])
def test_notification_profile_denial_precedes_downstream_call(
    monkeypatch: pytest.MonkeyPatch, profile_state: str
) -> None:
    monkeypatch.setattr(
        "app.schema.token_validator.validate",
        lambda _: Identity(subject=f"{profile_state}-subject"),
    )

    async def denied(_: str) -> EmployeeProfile:
        raise EmployeeForbiddenError

    async def forbidden_call(*_: object, **__: object) -> NotificationPage:
        pytest.fail("Notification Service must not be called")

    monkeypatch.setattr("app.schema.get_employee", denied)
    monkeypatch.setattr("app.schema.notification_list", forbidden_call)
    result = request(
        "POST",
        "/graphql",
        payload={"query": "{ notifications { nodes { id } } }"},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"] == [
        {
            "message": "Project access is not available for this account.",
            "extensions": {"code": "FORBIDDEN"},
        }
    ]


def test_notification_outage_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_admin(monkeypatch)

    async def unavailable(*_: object, **__: object) -> NotificationPage:
        raise NotificationUnavailableError("credential http://notification:8060 broker lease-token")

    monkeypatch.setattr("app.schema.notification_list", unavailable)
    result = request(
        "POST",
        "/graphql",
        payload={"query": "{ notifications { nodes { id } } }"},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"] == [
        {
            "message": "Notifications are temporarily unavailable.",
            "extensions": {"code": "SERVICE_UNAVAILABLE"},
        }
    ]
    assert "credential" not in str(result) and "notification:8060" not in str(result)


def test_report_request_dispatches_newly_submitted_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow_admin(monkeypatch)
    sequence: list[str] = []

    async def project(actor: EmployeeProfile, project_id: str) -> WorkProject:
        assert actor.id == "actor" and project_id == "project-id"
        sequence.append("project")
        return work_project()

    async def submit(actor: EmployeeProfile, **values: object) -> JobRecord:
        assert actor.id == "actor"
        assert values == {
            "project_id": "project-id",
            "include_completed": True,
            "idempotency_key": "phase11-report-request-0001",
        }
        sequence.append("submit")
        return job_record()

    async def dispatch(actor: EmployeeProfile, *, job_id: str, expected_version: int) -> JobRecord:
        assert actor.id == "actor"
        assert (job_id, expected_version) == ("job-id", 1)
        sequence.append("dispatch")
        return replace(job_record(), status="QUEUED", version=2)

    monkeypatch.setattr("app.schema.work_get_project", project)
    monkeypatch.setattr("app.schema.job_submit_job", submit)
    monkeypatch.setattr("app.schema.job_dispatch_job", dispatch)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": 'mutation { requestProjectTaskReport(input: {projectId: "project-id", includeCompleted: true, idempotencyKey: "phase11-report-request-0001"}) { id status version } }'
        },
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result.get("errors") is None
    assert result["data"]["requestProjectTaskReport"] == {
        "id": "job-id",
        "status": "QUEUED",
        "version": 2,
    }
    assert sequence == ["project", "submit", "dispatch"]


@pytest.mark.parametrize("role", ["ADMIN", "MANAGER", "MEMBER"])
def test_report_operations_forward_current_role_and_return_authorized_artifact(
    monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    allow_admin(monkeypatch, role)
    completed = replace(
        job_record(),
        status="SUCCEEDED",
        result_content="reference,title\nOPS-1,Export\n",
        result_content_type="text/csv; charset=utf-8",
        result_checksum="a" * 64,
        result_row_count=1,
        result_truncated=False,
    )

    async def get_job(actor: EmployeeProfile, _: str) -> JobRecord:
        assert actor.role == role and actor.id == "actor"
        return completed

    async def list_jobs(actor: EmployeeProfile, **_: object) -> JobPage:
        assert actor.role == role and actor.id == "actor"
        return JobPage([completed], None, False)

    monkeypatch.setattr("app.schema.job_get_job", get_job)
    monkeypatch.setattr("app.schema.job_list_jobs", list_jobs)
    result = request(
        "POST",
        "/graphql",
        payload={
            "query": '{ reports { nodes { id } } report(id: "job-id") { id } reportArtifact(id: "job-id") { contentType checksum content } }'
        },
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result.get("errors") is None
    assert result["data"]["reportArtifact"]["contentType"] == "text/csv; charset=utf-8"


@pytest.mark.parametrize("status", ["SUBMITTED", "FAILED"])
def test_pending_and_failed_reports_expose_no_artifact(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    allow_admin(monkeypatch)

    async def get_job(*_: object) -> JobRecord:
        return replace(job_record(), status=status)

    monkeypatch.setattr("app.schema.job_get_job", get_job)
    result = request(
        "POST",
        "/graphql",
        payload={"query": '{ reportArtifact(id: "job-id") { content } }'},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"] == [
        {
            "message": "The report artifact is not available.",
            "extensions": {"code": "ARTIFACT_UNAVAILABLE"},
        }
    ]


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("JOB_NOT_FOUND", "The job was not found."),
        ("IDEMPOTENCY_CONFLICT", "The idempotency key is already in use."),
        ("INVALID_CURSOR", "The job cursor is invalid."),
    ],
)
def test_report_domain_errors_are_typed_and_sanitized(
    monkeypatch: pytest.MonkeyPatch, code: str, message: str
) -> None:
    allow_admin(monkeypatch)

    async def denied(*_: object, **__: object) -> JobPage:
        raise JobDomainError(code, "raw internal URL credential broker metadata")

    monkeypatch.setattr("app.schema.job_list_jobs", denied)
    result = request(
        "POST",
        "/graphql",
        payload={"query": '{ reports(after: "invalid") { nodes { id } } }'},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"] == [{"message": message, "extensions": {"code": code}}]
    assert "credential" not in str(result) and "broker" not in str(result)


DASHBOARD_QUERY = """
query DashboardTest {
  dashboard {
    workAvailable
    jobAvailable
    projectMetrics {
      totalCount
      activeCount
      draftCount
      archivedCount
      managedTotalCount
      managedActiveCount
      managedDraftCount
      managedArchivedCount
    }
    taskMetrics {
      totalCount
      todoCount
      inProgressCount
      blockedCount
      doneCount
      cancelledCount
      overdueCount
    }
    assignedTaskMetrics {
      totalCount
      todoCount
      inProgressCount
      blockedCount
      doneCount
      cancelledCount
      overdueCount
    }
    recentProjects {
      id
      key
      name
      status
    }
    recentAssignedTasks {
      id
      projectId
      projectKey
      number
      title
      status
      priority
      dueDate
    }
    jobMetrics {
      totalCount
      submittedCount
      queuedCount
      runningCount
      succeededCount
      failedCount
      cancelledCount
    }
    recentJobs {
      id
      jobType
      status
    }
  }
}
"""


def mock_work_dashboard(role: str = "MEMBER") -> WorkDashboardMetrics:
    is_manager = role == "MANAGER"
    is_admin = role == "ADMIN"
    return WorkDashboardMetrics(
        project_metrics=WorkProjectMetrics(
            total_count=3,
            active_count=2,
            draft_count=1,
            archived_count=0,
            managed_total_count=2 if (is_manager or is_admin) else None,
            managed_active_count=1 if (is_manager or is_admin) else None,
            managed_draft_count=1 if (is_manager or is_admin) else None,
            managed_archived_count=0 if (is_manager or is_admin) else None,
        ),
        task_metrics=(
            WorkTaskMetrics(
                total_count=10,
                todo_count=4,
                in_progress_count=3,
                blocked_count=1,
                done_count=1,
                cancelled_count=1,
                overdue_count=2,
            )
            if (is_manager or is_admin)
            else None
        ),
        assigned_task_metrics=WorkTaskMetrics(
            total_count=5,
            todo_count=2,
            in_progress_count=1,
            blocked_count=1,
            done_count=1,
            cancelled_count=0,
            overdue_count=1,
        ),
        recent_projects=[
            WorkProject(
                id="proj-1",
                key="OPS",
                name="Operations",
                description=None,
                status="ACTIVE",
                creator_employee_id="actor",
                version=1,
                created_at="2026-10-14T00:00:00+00:00",
                updated_at="2026-10-14T00:00:00+00:00",
                memberships=[],
            )
        ],
        recent_assigned_tasks=[
            WorkDashboardTaskItem(
                id="task-1",
                project_id="proj-1",
                project_key="OPS",
                number=1,
                title="Assigned Task 1",
                status="TODO",
                priority="HIGH",
                due_date="2026-11-10",
                created_at="2026-10-14T00:00:00+00:00",
                updated_at="2026-10-14T00:00:00+00:00",
            )
        ],
    )


def mock_job_dashboard() -> JobDashboardMetrics:
    return JobDashboardMetrics(
        job_metrics=JobMetrics(
            total_count=4,
            submitted_count=1,
            queued_count=1,
            running_count=0,
            succeeded_count=1,
            failed_count=1,
            cancelled_count=0,
        ),
        recent_jobs=[
            JobRecord(
                id="job-1",
                job_type="PROJECT_TASK_EXPORT",
                status="SUCCEEDED",
                submitter_employee_id="actor",
                related_project_id="proj-1",
                payload={"projectId": "proj-1", "format": "CSV", "includeCompleted": True},
                result_summary="Exported 5 tasks",
                result_content=None,
                result_content_type=None,
                result_checksum=None,
                result_row_count=5,
                result_truncated=False,
                failure_classification=None,
                completed_at="2026-10-15T00:00:00+00:00",
                version=1,
                created_at="2026-10-15T00:00:00+00:00",
                updated_at="2026-10-15T00:00:00+00:00",
            )
        ],
    )


def test_dashboard_requires_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(_: str | None) -> Identity:
        raise AuthenticationError

    monkeypatch.setattr("app.schema.token_validator.validate", reject)
    result = request("POST", "/graphql", payload={"query": DASHBOARD_QUERY}).json()
    assert result["errors"] == [
        {"message": "Authentication is required.", "extensions": {"code": "UNAUTHENTICATED"}}
    ]


@pytest.mark.parametrize(
    ("error", "code", "message"),
    [
        (
            EmployeeForbiddenError(),
            "FORBIDDEN",
            "Project access is not available for this account.",
        ),
        (
            EmployeeUnavailableError(),
            "SERVICE_UNAVAILABLE",
            "Project access is temporarily unavailable.",
        ),
    ],
)
def test_dashboard_rejects_inactive_or_missing_profile(
    monkeypatch: pytest.MonkeyPatch, error: Exception, code: str, message: str
) -> None:
    monkeypatch.setattr(
        "app.schema.token_validator.validate", lambda _: Identity(subject="subject-1")
    )

    async def employee(_: str) -> EmployeeProfile:
        raise error

    monkeypatch.setattr("app.schema.get_employee", employee)
    result = request(
        "POST",
        "/graphql",
        payload={"query": DASHBOARD_QUERY},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"] == [{"message": message, "extensions": {"code": code}}]


def test_dashboard_member_role_aggregates(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_admin(monkeypatch, role="MEMBER")

    async def work_dash(actor: EmployeeProfile) -> WorkDashboardMetrics:
        return mock_work_dashboard("MEMBER")

    async def job_dash(actor: EmployeeProfile) -> JobDashboardMetrics:
        return mock_job_dashboard()

    monkeypatch.setattr("app.schema.work_get_dashboard_metrics", work_dash)
    monkeypatch.setattr("app.schema.job_get_dashboard_metrics", job_dash)

    result = request(
        "POST",
        "/graphql",
        payload={"query": DASHBOARD_QUERY},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result.get("errors") is None
    data = result["data"]["dashboard"]
    assert data["workAvailable"] is True
    assert data["jobAvailable"] is True
    assert data["taskMetrics"] is None  # MEMBER has no managed taskMetrics
    assert data["assignedTaskMetrics"]["totalCount"] == 5
    assert data["assignedTaskMetrics"]["overdueCount"] == 1
    assert data["projectMetrics"]["totalCount"] == 3
    assert data["projectMetrics"]["managedTotalCount"] is None
    assert len(data["recentProjects"]) == 1
    assert data["recentProjects"][0]["key"] == "OPS"
    assert len(data["recentAssignedTasks"]) == 1
    assert data["recentAssignedTasks"][0]["title"] == "Assigned Task 1"
    assert data["jobMetrics"]["totalCount"] == 4
    assert len(data["recentJobs"]) == 1


def test_dashboard_manager_role_aggregates(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_admin(monkeypatch, role="MANAGER")

    async def work_dash(actor: EmployeeProfile) -> WorkDashboardMetrics:
        return mock_work_dashboard("MANAGER")

    async def job_dash(actor: EmployeeProfile) -> JobDashboardMetrics:
        return mock_job_dashboard()

    monkeypatch.setattr("app.schema.work_get_dashboard_metrics", work_dash)
    monkeypatch.setattr("app.schema.job_get_dashboard_metrics", job_dash)

    result = request(
        "POST",
        "/graphql",
        payload={"query": DASHBOARD_QUERY},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result.get("errors") is None
    data = result["data"]["dashboard"]
    assert data["taskMetrics"]["totalCount"] == 10
    assert data["taskMetrics"]["overdueCount"] == 2
    assert data["assignedTaskMetrics"]["totalCount"] == 5
    assert data["projectMetrics"]["managedTotalCount"] == 2


def test_dashboard_admin_role_aggregates(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_admin(monkeypatch, role="ADMIN")

    async def work_dash(actor: EmployeeProfile) -> WorkDashboardMetrics:
        return mock_work_dashboard("ADMIN")

    async def job_dash(actor: EmployeeProfile) -> JobDashboardMetrics:
        return mock_job_dashboard()

    monkeypatch.setattr("app.schema.work_get_dashboard_metrics", work_dash)
    monkeypatch.setattr("app.schema.job_get_dashboard_metrics", job_dash)

    result = request(
        "POST",
        "/graphql",
        payload={"query": DASHBOARD_QUERY},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result.get("errors") is None
    data = result["data"]["dashboard"]
    assert data["taskMetrics"]["totalCount"] == 10
    assert data["jobMetrics"]["totalCount"] == 4


def test_dashboard_partial_failure_work_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_admin(monkeypatch, role="MEMBER")

    async def work_fail(actor: EmployeeProfile) -> WorkDashboardMetrics:
        raise WorkUnavailableError()

    async def job_dash(actor: EmployeeProfile) -> JobDashboardMetrics:
        return mock_job_dashboard()

    monkeypatch.setattr("app.schema.work_get_dashboard_metrics", work_fail)
    monkeypatch.setattr("app.schema.job_get_dashboard_metrics", job_dash)

    result = request(
        "POST",
        "/graphql",
        payload={"query": DASHBOARD_QUERY},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result.get("errors") is None
    data = result["data"]["dashboard"]
    assert data["workAvailable"] is False
    assert data["projectMetrics"] is None
    assert data["taskMetrics"] is None
    assert data["assignedTaskMetrics"] is None
    assert data["recentProjects"] is None
    assert data["recentAssignedTasks"] is None
    assert data["jobAvailable"] is True
    assert data["jobMetrics"]["totalCount"] == 4
    assert len(data["recentJobs"]) == 1


def test_dashboard_partial_failure_job_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_admin(monkeypatch, role="MEMBER")

    async def work_dash(actor: EmployeeProfile) -> WorkDashboardMetrics:
        return mock_work_dashboard("MEMBER")

    async def job_fail(actor: EmployeeProfile) -> JobDashboardMetrics:
        raise JobUnavailableError()

    monkeypatch.setattr("app.schema.work_get_dashboard_metrics", work_dash)
    monkeypatch.setattr("app.schema.job_get_dashboard_metrics", job_fail)

    result = request(
        "POST",
        "/graphql",
        payload={"query": DASHBOARD_QUERY},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result.get("errors") is None
    data = result["data"]["dashboard"]
    assert data["workAvailable"] is True
    assert data["projectMetrics"]["totalCount"] == 3
    assert data["jobAvailable"] is False
    assert data["jobMetrics"] is None
    assert data["recentJobs"] is None


def test_dashboard_both_services_fail_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_admin(monkeypatch, role="MEMBER")

    async def work_fail(actor: EmployeeProfile) -> WorkDashboardMetrics:
        raise WorkUnavailableError()

    async def job_fail(actor: EmployeeProfile) -> JobDashboardMetrics:
        raise JobUnavailableError()

    monkeypatch.setattr("app.schema.work_get_dashboard_metrics", work_fail)
    monkeypatch.setattr("app.schema.job_get_dashboard_metrics", job_fail)

    result = request(
        "POST",
        "/graphql",
        payload={"query": DASHBOARD_QUERY},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result["errors"] == [
        {
            "message": "Dashboard data is temporarily unavailable.",
            "extensions": {"code": "SERVICE_UNAVAILABLE"},
        }
    ]


def test_dashboard_downstream_requests_are_bounded_o1(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"employee": 0, "work": 0, "job": 0}

    monkeypatch.setattr(
        "app.schema.token_validator.validate", lambda _: Identity(subject="actor-subject")
    )

    async def actor(_: str) -> EmployeeProfile:
        calls["employee"] += 1
        return EmployeeProfile(
            id="actor", display_name="Actor", email="actor@example.test", role="MANAGER"
        )

    async def work_dash(_: EmployeeProfile) -> WorkDashboardMetrics:
        calls["work"] += 1
        return mock_work_dashboard("MANAGER")

    async def job_dash(_: EmployeeProfile) -> JobDashboardMetrics:
        calls["job"] += 1
        return mock_job_dashboard()

    monkeypatch.setattr("app.schema.get_employee", actor)
    monkeypatch.setattr("app.schema.work_get_dashboard_metrics", work_dash)
    monkeypatch.setattr("app.schema.job_get_dashboard_metrics", job_dash)

    result = request(
        "POST",
        "/graphql",
        payload={"query": DASHBOARD_QUERY},
        headers={"Authorization": "Bearer token"},
    ).json()
    assert result.get("errors") is None
    assert calls["employee"] == 1
    assert calls["work"] == 1
    assert calls["job"] == 1
    assert sum(calls.values()) == 3  # Strictly 3 downstream calls, O(1)
