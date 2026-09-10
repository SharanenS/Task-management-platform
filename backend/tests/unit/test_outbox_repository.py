"""Unit tests for OutboxRepository."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import OutboxEventType, OutboxStatus
from app.models.outbox import OutboxEvent
from app.repositories.outbox import OutboxRepository


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def repo(mock_session):
    return OutboxRepository(mock_session)


@pytest.fixture
def sample_event():
    return OutboxEvent(
        id=uuid.uuid4(),
        event_type=OutboxEventType.JOB_CREATED,
        aggregate_type="JOB",
        aggregate_id=uuid.uuid4(),
        payload={"job_id": str(uuid.uuid4())},
        status=OutboxStatus.PENDING,
        attempt_count=0,
        available_at=datetime.now(timezone.utc),
        last_error=None,
        published_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_create_outbox_event(repo, mock_session, sample_event):
    result = await repo.create(sample_event)

    assert result == sample_event
    mock_session.add.assert_called_once_with(sample_event)
    mock_session.flush.assert_called_once()
    mock_session.refresh.assert_called_once_with(sample_event)


@pytest.mark.asyncio
async def test_get_by_id(repo, mock_session, sample_event):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_event
    mock_session.execute.return_value = mock_result

    result = await repo.get_by_id(sample_event.id)

    assert result == sample_event
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_pending_events(repo, mock_session, sample_event):
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [sample_event]
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    events = await repo.get_pending_events(limit=10)

    assert len(events) == 1
    assert events[0] == sample_event
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_mark_published(repo, mock_session, sample_event):
    sample_event.status = OutboxStatus.PUBLISHED
    sample_event.published_at = datetime.now(timezone.utc)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_event
    mock_session.execute.return_value = mock_result

    updated = await repo.mark_published(sample_event.id)

    assert updated is not None
    assert updated.status == OutboxStatus.PUBLISHED
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_record_failure(repo, mock_session, sample_event):
    sample_event.attempt_count = 1
    sample_event.last_error = "Broker network error"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_event
    mock_session.execute.return_value = mock_result

    updated = await repo.record_failure(sample_event.id, "Broker network error")

    assert updated is not None
    assert updated.attempt_count == 1
    assert updated.last_error == "Broker network error"
    mock_session.execute.assert_called_once()
