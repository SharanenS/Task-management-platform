import hmac
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.models import JobStatus, JobType
from app.schemas import (
    JobAttemptPageResponse,
    JobAttemptResponse,
    JobPageResponse,
    JobResponse,
    JobSubmissionRequest,
)
from app.service import Actor, JobError, get_job, list_attempts, list_jobs, submit_job

app = FastAPI(title="Job Service", docs_url=None, redoc_url=None, openapi_url=None)
SessionDependency = Annotated[Session, Depends(get_session)]


def require_internal_service(x_internal_service_key: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_internal_service_key, settings.internal_service_key):
        raise HTTPException(status_code=403, detail="Forbidden")


def actor_context(
    x_actor_employee_id: str = Header(default=""),
    x_actor_application_role: str = Header(default=""),
) -> Actor:
    try:
        employee_id = UUID(x_actor_employee_id)
    except ValueError as error:
        raise HTTPException(status_code=403, detail="Forbidden") from error
    if x_actor_application_role not in {"ADMIN", "MANAGER", "MEMBER"}:
        raise HTTPException(status_code=403, detail="Forbidden")
    return Actor(employee_id, x_actor_application_role)


ActorDependency = Annotated[Actor, Depends(actor_context)]


def failure(error: JobError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code, detail={"code": error.code, "message": error.message}
    )


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def readiness(session: SessionDependency) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get(
    "/internal/jobs",
    response_model=JobPageResponse,
    dependencies=[Depends(require_internal_service)],
)
def directory(
    session: SessionDependency,
    actor: ActorDependency,
    first: int = Query(default=20, ge=1, le=50),
    after: str | None = None,
    status: JobStatus | None = None,
    job_type: JobType | None = None,
) -> JobPageResponse:
    try:
        page = list_jobs(session, actor, first=first, after=after, status=status, job_type=job_type)
        return JobPageResponse(
            items=[JobResponse.model_validate(item) for item in page.items],
            next_cursor=page.next_cursor,
            has_next_page=page.has_next_page,
        )
    except JobError as error:
        raise failure(error) from error


@app.get(
    "/internal/jobs/{job_id}",
    response_model=JobResponse,
    dependencies=[Depends(require_internal_service)],
)
def detail(job_id: UUID, session: SessionDependency, actor: ActorDependency) -> JobResponse:
    try:
        return JobResponse.model_validate(get_job(session, actor, job_id))
    except JobError as error:
        raise failure(error) from error


@app.get(
    "/internal/jobs/{job_id}/attempts",
    response_model=JobAttemptPageResponse,
    dependencies=[Depends(require_internal_service)],
)
def attempts(
    job_id: UUID, session: SessionDependency, actor: ActorDependency
) -> JobAttemptPageResponse:
    try:
        return JobAttemptPageResponse(
            items=[
                JobAttemptResponse.model_validate(item)
                for item in list_attempts(session, actor, job_id)
            ]
        )
    except JobError as error:
        raise failure(error) from error


@app.post(
    "/internal/jobs", response_model=JobResponse, dependencies=[Depends(require_internal_service)]
)
def submit(
    body: JobSubmissionRequest, session: SessionDependency, actor: ActorDependency
) -> JobResponse:
    try:
        return JobResponse.model_validate(submit_job(session, actor, body))
    except JobError as error:
        raise failure(error) from error
