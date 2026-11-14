import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import development_cleanup
from app.config import settings
from app.db import Base
from app.models import Job, JobStatus, JobType


def factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def add_job(values: sessionmaker[Session]) -> uuid.UUID:
    with values() as session:
        job = Job(
            job_type=JobType.PROJECT_TASK_EXPORT,
            status=JobStatus.SUBMITTED,
            submitter_employee_id=uuid.uuid4(),
            related_project_id=uuid.uuid4(),
            payload={"projectId": str(uuid.uuid4()), "format": "CSV", "includeCompleted": True},
            request_fingerprint="a" * 64,
            idempotency_key="phase6-cleanup-key",
        )
        session.add(job)
        session.commit()
        return job.id


def test_cleanup_removes_only_exact_job(monkeypatch: pytest.MonkeyPatch) -> None:
    values = factory()
    job_id = add_job(values)
    monkeypatch.setattr(development_cleanup, "SessionLocal", values)
    development_cleanup.remove(job_id)
    with values() as session:
        assert session.get(Job, job_id) is None


def test_cleanup_refuses_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(SystemExit, match="development or test"):
        development_cleanup.remove(uuid.uuid4())


def test_cleanup_refuses_unknown_exact_identifier(monkeypatch: pytest.MonkeyPatch) -> None:
    values = factory()
    monkeypatch.setattr(development_cleanup, "SessionLocal", values)
    with pytest.raises(SystemExit, match="exact job"):
        development_cleanup.remove(uuid.uuid4())
