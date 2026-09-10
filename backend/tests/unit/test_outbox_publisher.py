"""Unit tests for Outbox Publisher."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.constants import OutboxEventType, OutboxStatus
from app.models.outbox import OutboxEvent
from app.tasks.outbox_publisher import (
    publish_pending_events,
    publish_single_event,
)


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def sample_job_id():
    return uuid.uuid4()


@pytest.fixture
def sample_pending_event(sample_job_id):
    return OutboxEvent(
        id=uuid.uuid4(),
        event_type=OutboxEventType.JOB_CREATED,
        aggregate_type="JOB",
        aggregate_id=sample_job_id,
        payload={"job_id": str(sample_job_id)},
        status=OutboxStatus.PENDING,
        attempt_count=0,
        available_at=datetime.now(timezone.utc),
        last_error=None,
        published_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_publish_single_event_success(mock_session, sample_pending_event, sample_job_id):
    """Successful publication dispatches Celery task, marks PUBLISHED, and commits."""
    with (
        patch("app.tasks.jobs.process_job_task.delay") as mock_delay,
        patch("app.tasks.outbox_publisher.OutboxRepository") as mock_repo_cls,
    ):
        mock_repo = mock_repo_cls.return_value
        mock_repo.mark_published = AsyncMock(return_value=sample_pending_event)

        success = await publish_single_event(mock_session, sample_pending_event)

        assert success is True
        mock_delay.assert_called_once_with(str(sample_job_id))
        mock_repo.mark_published.assert_called_once_with(sample_pending_event.id)
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_publish_single_event_broker_failure(mock_session, sample_pending_event):
    """Broker failure records error details, keeps event PENDING, and commits failure state."""
    with (
        patch("app.tasks.jobs.process_job_task.delay", side_effect=RuntimeError("RabbitMQ unreachable")) as mock_delay,
        patch("app.tasks.outbox_publisher.OutboxRepository") as mock_repo_cls,
    ):
        mock_repo = mock_repo_cls.return_value
        mock_repo.record_failure = AsyncMock()

        success = await publish_single_event(mock_session, sample_pending_event)

        assert success is False
        mock_delay.assert_called_once()
        mock_session.rollback.assert_called_once()
        mock_repo.record_failure.assert_called_once_with(sample_pending_event.id, "RabbitMQ unreachable")
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_publish_single_event_unsupported_type(mock_session, sample_pending_event):
    """Unsupported event type records error and returns False."""
    sample_pending_event.event_type = "UNKNOWN_EVENT_TYPE"
    with patch("app.tasks.outbox_publisher.OutboxRepository") as mock_repo_cls:
        mock_repo = mock_repo_cls.return_value
        mock_repo.record_failure = AsyncMock()

        success = await publish_single_event(mock_session, sample_pending_event)

        assert success is False
        mock_repo.record_failure.assert_called_once()


@pytest.mark.asyncio
async def test_publish_pending_events_batch(mock_session, sample_pending_event):
    """Batch publisher claims pending events and returns count of published events."""
    with (
        patch("app.tasks.outbox_publisher.publisher_session_factory") as mock_factory,
        patch("app.tasks.outbox_publisher.OutboxRepository") as mock_repo_cls,
        patch("app.tasks.outbox_publisher.publish_single_event", return_value=True) as mock_pub_single,
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_repo = mock_repo_cls.return_value
        mock_repo.get_pending_events = AsyncMock(return_value=[sample_pending_event])

        published_count = await publish_pending_events(batch_size=10)

        assert published_count == 1
        mock_repo.get_pending_events.assert_called_once_with(limit=10)
        mock_pub_single.assert_called_once_with(mock_session, sample_pending_event)
