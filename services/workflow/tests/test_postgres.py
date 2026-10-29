import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import ExecutionStatus, SourceEvent, WorkflowExecution, WorkflowRule
from app.schemas import RuleCreate
from app.service import Actor, create_rule, receive_event, submit_pending_actions

DATABASE_URL = os.getenv("WORKFLOW_POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="WORKFLOW_POSTGRES_TEST_URL is required")


@pytest.fixture
def database() -> sessionmaker[Session]:
    assert DATABASE_URL
    engine = create_engine(DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.execute(delete(WorkflowExecution))
        session.execute(delete(SourceEvent))
        session.execute(delete(WorkflowRule))
        session.commit()
    yield factory
    with factory() as session:
        session.execute(delete(WorkflowExecution))
        session.execute(delete(SourceEvent))
        session.execute(delete(WorkflowRule))
        session.commit()
    engine.dispose()


def test_concurrent_duplicate_event_has_one_source_and_one_execution(
    database: sessionmaker[Session],
) -> None:
    project_id, event_id, task_id = uuid4(), uuid4(), uuid4()
    with database() as session:
        create_rule(
            session,
            Actor(uuid4(), "ADMIN"),
            RuleCreate(
                project_id=project_id,
                name="Concurrent",
                trigger_type="TASK_COMPLETED",
                action_type="PROJECT_TASK_EXPORT",
            ),
            None,
        )
    payload = {
        "eventId": str(event_id),
        "schemaVersion": 1,
        "eventType": "TASK_COMPLETED",
        "projectId": str(project_id),
        "taskId": str(task_id),
    }

    def deliver(_: int) -> None:
        with database() as session:
            receive_event(session, payload)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(deliver, range(8)))
    with database() as session:
        assert session.scalar(select(func.count()).select_from(SourceEvent)) == 1
        assert session.scalar(select(func.count()).select_from(WorkflowExecution)) == 1


def test_crash_after_job_acceptance_reuses_key_and_settles_original_job(
    database: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = uuid4()
    with database() as session:
        create_rule(
            session,
            Actor(uuid4(), "ADMIN"),
            RuleCreate(
                project_id=project_id,
                name="Crash boundary",
                trigger_type="TASK_COMPLETED",
                action_type="PROJECT_TASK_EXPORT",
            ),
            None,
        )
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
        execution_id = execution.id
    jobs: dict[str, str] = {}
    requests: list[str] = []

    class Response:
        def __init__(self, job_id: str):
            self.job_id = job_id

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"id": self.job_id}

    def post(*_: object, **kwargs: object) -> Response:
        key = kwargs["json"]["idempotency_key"]  # type: ignore[index]
        requests.append(key)
        jobs.setdefault(key, "11111111-1111-4111-8111-111111111111")
        return Response(jobs[key])

    monkeypatch.setattr("app.service.httpx.post", post)
    with database() as session:
        original_commit = session.commit

        def crash() -> None:
            raise RuntimeError("crash after accepted response")

        monkeypatch.setattr(session, "commit", crash)
        with pytest.raises(RuntimeError, match="crash after accepted"):
            submit_pending_actions(session)
        session.rollback()
        monkeypatch.setattr(session, "commit", original_commit)
        assert submit_pending_actions(session) == 1
    with database() as session:
        execution = session.get(WorkflowExecution, execution_id)
        assert execution and execution.status == ExecutionStatus.SUCCEEDED
        assert str(execution.resulting_job_id) == next(iter(jobs.values()))
        assert session.scalar(select(func.count()).select_from(WorkflowExecution)) == 1
    assert len(jobs) == 1
    assert requests == [f"workflow:{execution_id}", f"workflow:{execution_id}"]


def test_rule_delete_cascades_only_its_execution_and_preserves_source_and_other_rule(
    database: sessionmaker[Session],
) -> None:
    project_id, event_id = uuid4(), uuid4()
    with database() as session:
        first = create_rule(
            session,
            Actor(uuid4(), "ADMIN"),
            RuleCreate(
                project_id=project_id,
                name="First",
                trigger_type="TASK_COMPLETED",
                action_type="PROJECT_TASK_EXPORT",
            ),
            None,
        )
        second = create_rule(
            session,
            Actor(uuid4(), "ADMIN"),
            RuleCreate(
                project_id=project_id,
                name="Second",
                trigger_type="TASK_COMPLETED",
                action_type="PROJECT_TASK_EXPORT",
            ),
            None,
        )
        receive_event(
            session,
            {
                "eventId": str(event_id),
                "schemaVersion": 1,
                "eventType": "TASK_COMPLETED",
                "projectId": str(project_id),
                "taskId": str(uuid4()),
            },
        )
        first_id, second_id = first.id, second.id
    with database() as session:
        session.delete(session.get(WorkflowRule, first_id))
        session.commit()
    with database() as session:
        assert session.get(SourceEvent, event_id) is not None
        assert session.get(WorkflowRule, second_id) is not None
        assert (
            session.scalar(
                select(func.count())
                .select_from(WorkflowExecution)
                .where(WorkflowExecution.rule_id == first_id)
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(WorkflowExecution)
                .where(WorkflowExecution.rule_id == second_id)
            )
            == 1
        )
