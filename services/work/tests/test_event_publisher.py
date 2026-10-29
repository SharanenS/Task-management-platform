from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.event_publisher import settle_failure, settle_success
from app.models import WorkEventStatus, WorkOutboxEvent


def event() -> WorkOutboxEvent:
    return WorkOutboxEvent(
        event_type="TASK_COMPLETED",
        schema_version=1,
        project_id=uuid4(),
        task_id=uuid4(),
        actor_employee_id=uuid4(),
        task_version=2,
        status=WorkEventStatus.IN_FLIGHT,
        attempt_count=1,
        available_at=datetime.now(UTC),
        lease_token="current-token",
    )


def test_exact_token_settlement_and_stale_token_rejection() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        item = event()
        session.add(item)
        session.commit()
        assert not settle_success(session, item.id, "stale-token")
        assert item.status == WorkEventStatus.IN_FLIGHT
        assert settle_success(session, item.id, "current-token")
        assert item.status == WorkEventStatus.PUBLISHED and item.lease_token is None


def test_failure_is_bounded_and_stale_failure_cannot_regress_published_event() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        item = event()
        session.add(item)
        session.commit()
        assert settle_failure(session, item.id, "current-token")
        assert item.status == WorkEventStatus.FAILED
        assert item.last_failure_classification == "PUBLICATION_FAILED"
        assert not settle_failure(session, item.id, "current-token")
