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
        claimed_at=None,
        lease_until=None,
        claim_owner=None,
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
async def test_claim_events_empty(repo, mock_session):
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    claimed = await repo.claim_events(limit=10, lease_seconds=30, claim_owner="pub-1")

    assert len(claimed) == 0
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_claim_events_success(repo, mock_session, sample_event):
    sample_event.status = OutboxStatus.CLAIMED
    sample_event.claim_owner = "pub-1"
    sample_event.lease_until = datetime.now(timezone.utc)

    # First execute is select with for_update, second execute is update returning
    mock_select_res = MagicMock()
    mock_select_scalars = MagicMock()
    mock_select_scalars.all.return_value = [sample_event]
    mock_select_res.scalars.return_value = mock_select_scalars

    mock_update_res = MagicMock()
    mock_update_scalars = MagicMock()
    mock_update_scalars.all.return_value = [sample_event]
    mock_update_res.scalars.return_value = mock_update_scalars

    mock_session.execute.side_effect = [mock_select_res, mock_update_res]

    claimed = await repo.claim_events(limit=5, lease_seconds=30, claim_owner="pub-1")

    assert len(claimed) == 1
    assert claimed[0].status == OutboxStatus.CLAIMED
    assert claimed[0].claim_owner == "pub-1"
    assert mock_session.execute.call_count == 2


@pytest.mark.asyncio
async def test_mark_published_clears_lease(repo, mock_session, sample_event):
    sample_event.status = OutboxStatus.PUBLISHED
    sample_event.published_at = datetime.now(timezone.utc)
    sample_event.lease_until = None
    sample_event.claim_owner = None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_event
    mock_session.execute.return_value = mock_result

    updated = await repo.mark_published(sample_event.id, claim_owner="pub-1")

    assert updated is not None
    assert updated.status == OutboxStatus.PUBLISHED
    assert updated.lease_until is None
    assert updated.claim_owner is None
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_mark_published_rejects_stale_claim_owner(repo, mock_session, sample_event):
    """When settlement affects 0 rows because owner or lease expired, mark_published returns None."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    updated = await repo.mark_published(sample_event.id, claim_owner="stale-pub")

    assert updated is None
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_record_failure_clears_lease(repo, mock_session, sample_event):
    sample_event.status = OutboxStatus.PENDING
    sample_event.attempt_count = 1
    sample_event.last_error = "Broker network error"
    sample_event.lease_until = None
    sample_event.claim_owner = None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_event
    mock_session.execute.return_value = mock_result

    updated = await repo.record_failure(sample_event.id, "Broker network error", claim_owner="pub-1")

    assert updated is not None
    assert updated.status == OutboxStatus.PENDING
    assert updated.attempt_count == 1
    assert updated.last_error == "Broker network error"
    assert updated.lease_until is None
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_record_failure_rejects_stale_claim_owner(repo, mock_session, sample_event):
    """When recording failure affects 0 rows because owner or lease expired, returns None."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    updated = await repo.record_failure(sample_event.id, "Broker network error", claim_owner="stale-pub")

    assert updated is None
    mock_session.execute.assert_called_once()
