import hmac
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.schemas import (
    ExecutionPage,
    ExecutionResponse,
    RuleCreate,
    RulePage,
    RuleResponse,
    RuleStateUpdate,
    RuleUpdate,
)
from app.service import (
    Actor,
    WorkflowError,
    create_rule,
    get_execution,
    get_rule,
    list_executions,
    list_rules,
    update_rule,
)

app = FastAPI(title="Workflow Service", docs_url=None, redoc_url=None, openapi_url=None)
SessionDependency = Annotated[Session, Depends(get_session)]


def require_internal(x_internal_service_key: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_internal_service_key, settings.internal_service_key):
        raise HTTPException(403, "Forbidden")


def actor_context(
    x_actor_employee_id: str = Header(default=""),
    x_actor_application_role: str = Header(default=""),
) -> Actor:
    try:
        identifier = UUID(x_actor_employee_id)
    except ValueError as error:
        raise HTTPException(403, "Forbidden") from error
    if x_actor_application_role not in {"ADMIN", "MANAGER", "MEMBER"}:
        raise HTTPException(403, "Forbidden")
    return Actor(identifier, x_actor_application_role)


ActorDependency = Annotated[Actor, Depends(actor_context)]


def ids(value: str | None) -> set[UUID]:
    if not value:
        return set()
    try:
        return {UUID(item) for item in value.split(",") if item}
    except ValueError as error:
        raise HTTPException(403, "Forbidden") from error


def failure(error: WorkflowError) -> HTTPException:
    return HTTPException(error.status_code, {"code": error.code, "message": error.message})


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def ready(session: SessionDependency) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get("/internal/rules", response_model=RulePage, dependencies=[Depends(require_internal)])
def rules(
    session: SessionDependency,
    actor: ActorDependency,
    first: int = Query(20, ge=1, le=50),
    after: str | None = None,
    project_id: UUID | None = None,
    enabled: bool | None = None,
    x_actor_project_ids: str | None = Header(default=None),
) -> RulePage:
    try:
        page = list_rules(
            session,
            actor,
            project_ids=ids(x_actor_project_ids),
            first=first,
            after=after,
            project_id=project_id,
            enabled=enabled,
        )
        return RulePage(
            items=[RuleResponse.model_validate(item) for item in page.items],
            next_cursor=page.next_cursor,
            has_next_page=page.has_next_page,
        )
    except WorkflowError as error:
        raise failure(error) from error


@app.get(
    "/internal/rules/{rule_id}",
    response_model=RuleResponse,
    dependencies=[Depends(require_internal)],
)
def rule(
    rule_id: UUID,
    session: SessionDependency,
    actor: ActorDependency,
    x_actor_project_ids: str | None = Header(default=None),
) -> RuleResponse:
    try:
        return RuleResponse.model_validate(
            get_rule(session, actor, rule_id, ids(x_actor_project_ids))
        )
    except WorkflowError as error:
        raise failure(error) from error


@app.post("/internal/rules", response_model=RuleResponse, dependencies=[Depends(require_internal)])
def create(
    body: RuleCreate,
    session: SessionDependency,
    actor: ActorDependency,
    x_actor_managed_project_ids: str | None = Header(default=None),
) -> RuleResponse:
    try:
        return RuleResponse.model_validate(
            create_rule(session, actor, body, ids(x_actor_managed_project_ids))
        )
    except WorkflowError as error:
        raise failure(error) from error


@app.put(
    "/internal/rules/{rule_id}",
    response_model=RuleResponse,
    dependencies=[Depends(require_internal)],
)
def update(
    rule_id: UUID,
    body: RuleUpdate,
    session: SessionDependency,
    actor: ActorDependency,
    x_actor_managed_project_ids: str | None = Header(default=None),
) -> RuleResponse:
    try:
        return RuleResponse.model_validate(
            update_rule(
                session,
                actor,
                rule_id,
                name=body.name,
                enabled=None,
                expected_version=body.expected_version,
                managed_project_ids=ids(x_actor_managed_project_ids),
            )
        )
    except WorkflowError as error:
        raise failure(error) from error


@app.put(
    "/internal/rules/{rule_id}/state",
    response_model=RuleResponse,
    dependencies=[Depends(require_internal)],
)
def state(
    rule_id: UUID,
    body: RuleStateUpdate,
    session: SessionDependency,
    actor: ActorDependency,
    x_actor_managed_project_ids: str | None = Header(default=None),
) -> RuleResponse:
    try:
        return RuleResponse.model_validate(
            update_rule(
                session,
                actor,
                rule_id,
                name=None,
                enabled=body.enabled,
                expected_version=body.expected_version,
                managed_project_ids=ids(x_actor_managed_project_ids),
            )
        )
    except WorkflowError as error:
        raise failure(error) from error


@app.get(
    "/internal/executions", response_model=ExecutionPage, dependencies=[Depends(require_internal)]
)
def executions(
    session: SessionDependency,
    actor: ActorDependency,
    first: int = Query(20, ge=1, le=50),
    after: str | None = None,
    rule_id: UUID | None = None,
    x_actor_project_ids: str | None = Header(default=None),
) -> ExecutionPage:
    page = list_executions(
        session,
        actor,
        project_ids=ids(x_actor_project_ids),
        first=first,
        after=after,
        rule_id=rule_id,
    )
    return ExecutionPage(
        items=[ExecutionResponse.model_validate(item) for item in page.items],
        next_cursor=page.next_cursor,
        has_next_page=page.has_next_page,
    )


@app.get(
    "/internal/executions/{execution_id}",
    response_model=ExecutionResponse,
    dependencies=[Depends(require_internal)],
)
def execution(
    execution_id: UUID,
    session: SessionDependency,
    actor: ActorDependency,
    x_actor_project_ids: str | None = Header(default=None),
) -> ExecutionResponse:
    try:
        return ExecutionResponse.model_validate(
            get_execution(session, actor, execution_id, ids(x_actor_project_ids))
        )
    except WorkflowError as error:
        raise failure(error) from error
