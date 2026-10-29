import base64
import binascii
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import and_, or_, select, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.config import settings
from app.models import (
    ActionType,
    ExecutionStatus,
    InboxStatus,
    SourceEvent,
    TriggerType,
    WorkflowExecution,
    WorkflowRule,
)
from app.schemas import RuleCreate


class WorkflowError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code


@dataclass(frozen=True)
class Actor:
    employee_id: UUID
    application_role: str


@dataclass(frozen=True)
class Page:
    items: list[WorkflowRule] | list[WorkflowExecution]
    next_cursor: str | None
    has_next_page: bool


def _cursor(value: WorkflowRule | WorkflowExecution) -> str:
    created_at = value.created_at
    identifier = value.id
    raw = json.dumps([created_at.isoformat(), str(identifier)], separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode(value: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        timestamp, identifier = json.loads(raw)
        return datetime.fromisoformat(timestamp), UUID(identifier)
    except (ValueError, TypeError, json.JSONDecodeError, binascii.Error) as error:
        raise WorkflowError("INVALID_CURSOR", "The workflow cursor is invalid.") from error


def _viewable(actor: Actor, project_ids: set[UUID] | None) -> ColumnElement[bool]:
    if actor.application_role == "ADMIN":
        return true()
    return WorkflowRule.project_id.in_(project_ids or set())


def list_rules(
    session: Session,
    actor: Actor,
    *,
    project_ids: set[UUID] | None,
    first: int,
    after: str | None,
    project_id: UUID | None,
    enabled: bool | None,
) -> Page:
    if first < 1 or first > 50:
        raise WorkflowError("INVALID_PAGE_SIZE", "The page size must be between 1 and 50.")
    query = select(WorkflowRule).where(_viewable(actor, project_ids))
    if project_id:
        query = query.where(WorkflowRule.project_id == project_id)
    if enabled is not None:
        query = query.where(WorkflowRule.enabled == enabled)
    if after:
        created, identifier = _decode(after)
        query = query.where(
            or_(
                WorkflowRule.created_at < created,
                and_(WorkflowRule.created_at == created, WorkflowRule.id < identifier),
            )
        )
    items = list(
        session.scalars(
            query.order_by(WorkflowRule.created_at.desc(), WorkflowRule.id.desc()).limit(first + 1)
        )
    )
    return Page(
        items[:first], _cursor(items[first - 1]) if len(items) > first else None, len(items) > first
    )


def get_rule(
    session: Session, actor: Actor, rule_id: UUID, project_ids: set[UUID] | None
) -> WorkflowRule:
    rule = session.get(WorkflowRule, rule_id)
    if not rule or (
        actor.application_role != "ADMIN" and rule.project_id not in (project_ids or set())
    ):
        raise WorkflowError("NOT_FOUND", "The workflow rule was not found.", 404)
    return rule


def create_rule(
    session: Session, actor: Actor, body: RuleCreate, managed_project_ids: set[UUID] | None
) -> WorkflowRule:
    if actor.application_role != "ADMIN" and body.project_id not in (managed_project_ids or set()):
        raise WorkflowError("FORBIDDEN", "Workflow management is not permitted.", 403)
    rule = WorkflowRule(**body.model_dump(), creator_employee_id=actor.employee_id)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def update_rule(
    session: Session,
    actor: Actor,
    rule_id: UUID,
    *,
    name: str | None,
    enabled: bool | None,
    expected_version: int,
    managed_project_ids: set[UUID] | None,
) -> WorkflowRule:
    rule = session.scalar(select(WorkflowRule).where(WorkflowRule.id == rule_id).with_for_update())
    if not rule:
        raise WorkflowError("NOT_FOUND", "The workflow rule was not found.", 404)
    if actor.application_role != "ADMIN" and rule.project_id not in (managed_project_ids or set()):
        raise WorkflowError("NOT_FOUND", "The workflow rule was not found.", 404)
    if rule.version != expected_version:
        raise WorkflowError("VERSION_CONFLICT", "The workflow rule changed; reload and retry.", 409)
    if name is not None:
        normalized = " ".join(name.split())
        if not normalized or len(normalized) > 200:
            raise WorkflowError("INVALID_INPUT", "The workflow name is invalid.")
        rule.name = normalized
    if enabled is not None:
        rule.enabled = enabled
    rule.version += 1
    session.commit()
    session.refresh(rule)
    return rule


def list_executions(
    session: Session,
    actor: Actor,
    *,
    project_ids: set[UUID] | None,
    first: int,
    after: str | None,
    rule_id: UUID | None,
) -> Page:
    query = select(WorkflowExecution).join(WorkflowRule).where(_viewable(actor, project_ids))
    if rule_id:
        query = query.where(WorkflowExecution.rule_id == rule_id)
    if after:
        created, identifier = _decode(after)
        query = query.where(
            or_(
                WorkflowExecution.created_at < created,
                and_(WorkflowExecution.created_at == created, WorkflowExecution.id < identifier),
            )
        )
    items = list(
        session.scalars(
            query.order_by(WorkflowExecution.created_at.desc(), WorkflowExecution.id.desc()).limit(
                min(max(first, 1), 50) + 1
            )
        )
    )
    limit = min(max(first, 1), 50)
    return Page(
        items[:limit], _cursor(items[limit - 1]) if len(items) > limit else None, len(items) > limit
    )


def get_execution(
    session: Session, actor: Actor, execution_id: UUID, project_ids: set[UUID] | None
) -> WorkflowExecution:
    item = session.get(WorkflowExecution, execution_id)
    if not item or (
        actor.application_role != "ADMIN" and item.project_id not in (project_ids or set())
    ):
        raise WorkflowError("NOT_FOUND", "The workflow execution was not found.", 404)
    return item


def receive_event(session: Session, payload: dict[str, object]) -> list[WorkflowExecution]:
    try:
        event_id, project_id, task_id = (
            UUID(str(payload["eventId"])),
            UUID(str(payload["projectId"])),
            UUID(str(payload["taskId"])),
        )
        event_type = str(payload["eventType"])
        raw_schema_version = payload["schemaVersion"]
        if not isinstance(raw_schema_version, int):
            raise ValueError
        schema_version = raw_schema_version
    except (KeyError, ValueError, TypeError) as error:
        raise WorkflowError("INVALID_EVENT", "The workflow event is invalid.") from error
    existing = session.get(SourceEvent, event_id)
    if existing and existing.status != InboxStatus.RECEIVED:
        return list(
            session.scalars(
                select(WorkflowExecution).where(WorkflowExecution.source_event_id == event_id)
            )
        )
    supported = event_type == "TASK_COMPLETED" and schema_version == 1
    source = SourceEvent(
        id=event_id,
        schema_version=schema_version,
        event_type=event_type,
        project_id=project_id,
        task_id=task_id,
        status=InboxStatus.RECEIVED if supported else InboxStatus.QUARANTINED,
        failure_classification=None if supported else "UNSUPPORTED_EVENT",
    )
    if existing is None:
        session.add(source)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = session.get(SourceEvent, event_id)
            if existing is None:
                raise
            if existing.status != InboxStatus.RECEIVED:
                return list(
                    session.scalars(
                        select(WorkflowExecution).where(
                            WorkflowExecution.source_event_id == event_id
                        )
                    )
                )
            source = existing
    else:
        source = existing
    if not supported or source.status == InboxStatus.QUARANTINED:
        return []
    executions = [
        WorkflowExecution(
            rule_id=rule.id, source_event_id=event_id, project_id=project_id, task_id=task_id
        )
        for rule in session.scalars(
            select(WorkflowRule).where(
                WorkflowRule.project_id == project_id,
                WorkflowRule.enabled.is_(True),
                WorkflowRule.trigger_type == TriggerType.TASK_COMPLETED,
                WorkflowRule.action_type == ActionType.PROJECT_TASK_EXPORT,
            )
        )
    ]
    session.add_all(executions)
    source.status = InboxStatus.PROCESSED
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
    return list(
        session.scalars(
            select(WorkflowExecution).where(WorkflowExecution.source_event_id == event_id)
        )
    )


def submit_pending_actions(session: Session) -> int:
    processed = 0
    for execution in session.scalars(
        select(WorkflowExecution)
        .where(WorkflowExecution.status == ExecutionStatus.PENDING)
        .order_by(WorkflowExecution.created_at)
        .limit(20)
    ):
        rule = session.get(WorkflowRule, execution.rule_id)
        if rule is None:
            execution.status = ExecutionStatus.FAILED
            execution.failure_classification = "RULE_UNAVAILABLE"
            execution.completed_at = datetime.now(UTC)
            session.commit()
            continue
        try:
            response = httpx.post(
                f"{settings.job_service_url}/internal/workflow/jobs",
                headers={
                    "X-Workflow-Service-Key": settings.job_workflow_service_key,
                    "X-Workflow-Actor-Employee-Id": str(rule.creator_employee_id),
                },
                json={
                    "job_type": "PROJECT_TASK_EXPORT",
                    "payload": {
                        "project_id": str(execution.project_id),
                        "format": "CSV",
                        "include_completed": True,
                    },
                    "idempotency_key": f"workflow:{execution.id}",
                },
                timeout=8.0,
            )
            response.raise_for_status()
            execution.resulting_job_id = UUID(response.json()["id"])
            execution.status = ExecutionStatus.SUCCEEDED
            execution.completed_at = datetime.now(UTC)
            execution.failure_classification = None
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            execution.failure_classification = "ACTION_UNAVAILABLE"
        session.commit()
        processed += 1
    return processed
