from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import ExecutionStatus, InboxStatus, SourceEvent, WorkflowExecution
from app.schemas import RuleCreate
from app.service import (
    Actor,
    WorkflowError,
    create_rule,
    get_execution,
    get_rule,
    list_rules,
    receive_event,
    submit_pending_actions,
    update_rule,
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


def body(project_id: object, name: str = "Export completed tasks") -> RuleCreate:
    return RuleCreate(
        project_id=project_id,
        name=name,
        trigger_type="TASK_COMPLETED",
        action_type="PROJECT_TASK_EXPORT",
    )


def test_manager_can_manage_only_managed_project_and_version_is_optimistic(
    session: Session,
) -> None:
    actor, project_id = Actor(uuid4(), "MANAGER"), uuid4()
    with pytest.raises(WorkflowError) as denied:
        create_rule(session, actor, body(project_id), set())
    assert denied.value.code == "FORBIDDEN"
    rule = create_rule(session, actor, body(project_id, "  Export   completed  "), {project_id})
    assert rule.name == "Export completed"
    changed = update_rule(
        session,
        actor,
        rule.id,
        name=None,
        enabled=False,
        expected_version=1,
        managed_project_ids={project_id},
    )
    assert not changed.enabled and changed.version == 2
    with pytest.raises(WorkflowError) as conflict:
        update_rule(
            session,
            actor,
            rule.id,
            name="Old",
            enabled=None,
            expected_version=1,
            managed_project_ids={project_id},
        )
    assert conflict.value.code == "VERSION_CONFLICT"


def test_visibility_pagination_and_bounded_page_size(session: Session) -> None:
    admin, project_id = Actor(uuid4(), "ADMIN"), uuid4()
    for number in range(3):
        create_rule(session, admin, body(project_id, f"Rule {number}"), None)
    page = list_rules(
        session,
        Actor(uuid4(), "MEMBER"),
        project_ids={project_id},
        first=2,
        after=None,
        project_id=None,
        enabled=None,
    )
    assert len(page.items) == 2 and page.has_next_page and page.next_cursor
    second = list_rules(
        session,
        admin,
        project_ids=None,
        first=2,
        after=page.next_cursor,
        project_id=None,
        enabled=None,
    )
    assert len(second.items) == 1
    with pytest.raises(WorkflowError) as invalid:
        list_rules(
            session, admin, project_ids=None, first=51, after=None, project_id=None, enabled=None
        )
    assert invalid.value.code == "INVALID_PAGE_SIZE"


def test_admin_override_member_read_and_concealed_nonmember_mutation(session: Session) -> None:
    project_id = uuid4()
    admin = Actor(uuid4(), "ADMIN")
    rule = create_rule(session, admin, body(project_id), None)
    assert get_rule(session, Actor(uuid4(), "MEMBER"), rule.id, {project_id}).id == rule.id
    with pytest.raises(WorkflowError) as concealed:
        get_rule(session, Actor(uuid4(), "MEMBER"), rule.id, set())
    assert concealed.value.code == "NOT_FOUND"
    with pytest.raises(WorkflowError) as denied:
        update_rule(
            session,
            Actor(uuid4(), "MEMBER"),
            rule.id,
            name="Denied",
            enabled=None,
            expected_version=1,
            managed_project_ids=set(),
        )
    assert denied.value.code == "NOT_FOUND"


def test_invalid_cursor_and_execution_concealment(session: Session) -> None:
    project_id = uuid4()
    create_rule(session, Actor(uuid4(), "ADMIN"), body(project_id), None)
    with pytest.raises(WorkflowError) as invalid:
        list_rules(
            session,
            Actor(uuid4(), "ADMIN"),
            project_ids=None,
            first=10,
            after="not-a-cursor",
            project_id=None,
            enabled=None,
        )
    assert invalid.value.code == "INVALID_CURSOR"
    execution = receive_event(
        session,
        {
            "eventId": str(uuid4()),
            "schemaVersion": 1,
            "eventType": "TASK_COMPLETED",
            "projectId": str(project_id),
            "taskId": str(uuid4()),
        },
    )[0]
    with pytest.raises(WorkflowError) as concealed:
        get_execution(session, Actor(uuid4(), "MEMBER"), execution.id, set())
    assert concealed.value.code == "NOT_FOUND"


def test_duplicate_delivery_creates_one_execution_per_enabled_matching_rule(
    session: Session,
) -> None:
    project_id, event_id = uuid4(), uuid4()
    admin = Actor(uuid4(), "ADMIN")
    create_rule(session, admin, body(project_id, "First"), None)
    disabled = create_rule(session, admin, body(project_id, "Disabled"), None)
    update_rule(
        session,
        admin,
        disabled.id,
        name=None,
        enabled=False,
        expected_version=1,
        managed_project_ids=None,
    )
    create_rule(session, admin, body(project_id, "Second"), None)
    payload = {
        "eventId": str(event_id),
        "schemaVersion": 1,
        "eventType": "TASK_COMPLETED",
        "projectId": str(project_id),
        "taskId": str(uuid4()),
    }
    assert len(receive_event(session, payload)) == 2
    assert len(receive_event(session, payload)) == 2
    assert session.scalar(select(func.count()).select_from(WorkflowExecution)) == 2


def test_unsupported_contract_is_quarantined_without_execution(session: Session) -> None:
    event_id = uuid4()
    assert (
        receive_event(
            session,
            {
                "eventId": str(event_id),
                "schemaVersion": 2,
                "eventType": "TASK_COMPLETED",
                "projectId": str(uuid4()),
                "taskId": str(uuid4()),
            },
        )
        == []
    )
    event = session.get(SourceEvent, event_id)
    assert event and event.status == InboxStatus.QUARANTINED
    assert event.failure_classification == "UNSUPPORTED_EVENT"


@pytest.mark.parametrize(
    ("event_type", "schema_version"),
    [("UNKNOWN", 1), ("TASK_COMPLETED", 99)],
)
def test_each_unsupported_contract_dimension_is_quarantined(
    session: Session, event_type: str, schema_version: int
) -> None:
    assert (
        receive_event(
            session,
            {
                "eventId": str(uuid4()),
                "schemaVersion": schema_version,
                "eventType": event_type,
                "projectId": str(uuid4()),
                "taskId": str(uuid4()),
            },
        )
        == []
    )


def test_action_retry_uses_execution_derived_idempotency_and_links_one_job(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = uuid4()
    create_rule(session, Actor(uuid4(), "ADMIN"), body(project_id), None)
    execution = receive_event(
        session,
        {
            "eventId": str(uuid4()),
            "schemaVersion": 1,
            "eventType": "TASK_COMPLETED",
            "projectId": str(project_id),
            "taskId": str(uuid4()),
        },
    )[0]
    requests: list[dict[str, object]] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"id": "11111111-1111-4111-8111-111111111111"}

    def post(*_: object, **kwargs: object) -> Response:
        requests.append(kwargs["json"])  # type: ignore[arg-type]
        return Response()

    monkeypatch.setattr("app.service.httpx.post", post)
    assert submit_pending_actions(session) == 1
    session.refresh(execution)
    assert execution.status == ExecutionStatus.SUCCEEDED
    assert str(execution.resulting_job_id) == "11111111-1111-4111-8111-111111111111"
    assert requests[0]["idempotency_key"] == f"workflow:{execution.id}"
    assert submit_pending_actions(session) == 0


def test_job_unavailable_then_retry_recovers_with_same_idempotency_key(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = uuid4()
    create_rule(session, Actor(uuid4(), "ADMIN"), body(project_id), None)
    execution = receive_event(
        session,
        {
            "eventId": str(uuid4()),
            "schemaVersion": 1,
            "eventType": "TASK_COMPLETED",
            "projectId": str(project_id),
            "taskId": str(uuid4()),
        },
    )[0]
    requests: list[str] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"id": "11111111-1111-4111-8111-111111111111"}

    def post(*_: object, **kwargs: object) -> Response:
        requests.append(kwargs["json"]["idempotency_key"])  # type: ignore[index]
        if len(requests) == 1:
            raise httpx.ConnectError("sensitive upstream detail")
        return Response()

    import httpx

    monkeypatch.setattr("app.service.httpx.post", post)
    submit_pending_actions(session)
    session.refresh(execution)
    assert execution.status == ExecutionStatus.PENDING
    assert execution.failure_classification == "ACTION_UNAVAILABLE"
    submit_pending_actions(session)
    session.refresh(execution)
    assert execution.status == ExecutionStatus.SUCCEEDED
    assert requests == [f"workflow:{execution.id}", f"workflow:{execution.id}"]
