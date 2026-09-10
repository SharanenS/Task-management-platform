"""Unit tests for Outbox Publisher with Lease/Claim Mechanism."""

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.constants import OutboxEventType, OutboxStatus
from app.models.outbox import OutboxEvent
from app.tasks.outbox_publisher import (
    claim_batch,
    publish_pending_events,
    publish_single_event,
    run_publisher_loop,
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
def sample_claimed_event(sample_job_id):
    return OutboxEvent(
        id=uuid.uuid4(),
        event_type=OutboxEventType.JOB_CREATED,
        aggregate_type="JOB",
        aggregate_id=sample_job_id,
        payload={"job_id": str(sample_job_id)},
        status=OutboxStatus.CLAIMED,
        attempt_count=0,
        available_at=datetime.now(timezone.utc),
        claimed_at=datetime.now(timezone.utc),
        lease_until=datetime.now(timezone.utc),
        claim_owner="test-publisher",
        last_error=None,
        published_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_claim_batch_commits_immediately(mock_session, sample_claimed_event):
    """Claiming a batch of events commits the session immediately to release DB row locks."""
    with patch("app.tasks.outbox_publisher.OutboxRepository") as mock_repo_cls:
        mock_repo = mock_repo_cls.return_value
        mock_repo.claim_events = AsyncMock(return_value=[sample_claimed_event])

        events = await claim_batch(batch_size=10, lease_seconds=30, publisher_id="p-1", session=mock_session)

        assert len(events) == 1
        mock_repo.claim_events.assert_called_once_with(limit=10, lease_seconds=30, claim_owner="p-1")
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_publish_single_event_success(mock_session, sample_claimed_event, sample_job_id):
    """Successful publication dispatches Celery task, marks PUBLISHED with owner, and commits."""
    with (
        patch("app.tasks.jobs.process_job_task.delay") as mock_delay,
        patch("app.tasks.outbox_publisher.OutboxRepository") as mock_repo_cls,
    ):
        mock_repo = mock_repo_cls.return_value
        mock_repo.mark_published = AsyncMock(return_value=sample_claimed_event)

        success = await publish_single_event(
            sample_claimed_event,
            claim_owner="test-publisher",
            session=mock_session,
        )

        assert success is True
        mock_delay.assert_called_once_with(str(sample_job_id))
        mock_repo.mark_published.assert_called_once_with(
            event_id=sample_claimed_event.id,
            claim_owner="test-publisher",
        )
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_publish_single_event_stale_owner_returns_false(mock_session, sample_claimed_event, sample_job_id):
    """When settlement returns None because ownership was lost, publish_single_event returns False."""
    with (
        patch("app.tasks.jobs.process_job_task.delay") as mock_delay,
        patch("app.tasks.outbox_publisher.OutboxRepository") as mock_repo_cls,
    ):
        mock_repo = mock_repo_cls.return_value
        mock_repo.mark_published = AsyncMock(return_value=None)

        success = await publish_single_event(
            sample_claimed_event,
            claim_owner="stale-publisher",
            session=mock_session,
        )

        assert success is False
        mock_delay.assert_called_once_with(str(sample_job_id))
        mock_repo.mark_published.assert_called_once_with(
            event_id=sample_claimed_event.id,
            claim_owner="stale-publisher",
        )
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_publish_single_event_broker_failure(mock_session, sample_claimed_event):
    """Broker failure records error details, resets to PENDING with owner, and commits failure state."""
    with (
        patch("app.tasks.jobs.process_job_task.delay", side_effect=RuntimeError("RabbitMQ unreachable")) as mock_delay,
        patch("app.tasks.outbox_publisher.OutboxRepository") as mock_repo_cls,
    ):
        mock_repo = mock_repo_cls.return_value
        mock_repo.record_failure = AsyncMock(return_value=sample_claimed_event)

        success = await publish_single_event(
            sample_claimed_event,
            claim_owner="test-publisher",
            session=mock_session,
        )

        assert success is False
        mock_delay.assert_called_once()
        mock_session.rollback.assert_called_once()
        mock_repo.record_failure.assert_called_once_with(
            event_id=sample_claimed_event.id,
            error_message="RabbitMQ unreachable",
            claim_owner="test-publisher",
        )
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_publish_single_event_broker_failure_lost_ownership(mock_session, sample_claimed_event):
    """Broker failure when ownership is lost handles None return safely and returns False."""
    with (
        patch("app.tasks.jobs.process_job_task.delay", side_effect=RuntimeError("RabbitMQ unreachable")) as mock_delay,
        patch("app.tasks.outbox_publisher.OutboxRepository") as mock_repo_cls,
    ):
        mock_repo = mock_repo_cls.return_value
        mock_repo.record_failure = AsyncMock(return_value=None)

        success = await publish_single_event(
            sample_claimed_event,
            claim_owner="stale-publisher",
            session=mock_session,
        )

        assert success is False
        mock_repo.record_failure.assert_called_once_with(
            event_id=sample_claimed_event.id,
            error_message="RabbitMQ unreachable",
            claim_owner="stale-publisher",
        )
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_publish_single_event_unsupported_type(mock_session, sample_claimed_event):
    """Unsupported event type records error and returns False."""
    sample_claimed_event.event_type = "UNKNOWN_EVENT_TYPE"
    with patch("app.tasks.outbox_publisher.OutboxRepository") as mock_repo_cls:
        mock_repo = mock_repo_cls.return_value
        mock_repo.record_failure = AsyncMock()

        success = await publish_single_event(
            sample_claimed_event,
            claim_owner="test-publisher",
            session=mock_session,
        )

        assert success is False
        mock_repo.record_failure.assert_called_once()


@pytest.mark.asyncio
async def test_publish_pending_events_pipeline(sample_claimed_event):
    """Batch publisher claims eligible events and passes claim_owner to publish_single_event."""
    with (
        patch("app.tasks.outbox_publisher.claim_batch", return_value=[sample_claimed_event]) as mock_claim,
        patch("app.tasks.outbox_publisher.publish_single_event", return_value=True) as mock_pub_single,
    ):
        published_count = await publish_pending_events(batch_size=10, lease_seconds=25, publisher_id="pub-1")

        assert published_count == 1
        mock_claim.assert_called_once_with(batch_size=10, lease_seconds=25, publisher_id="pub-1")
        mock_pub_single.assert_called_once_with(
            event=sample_claimed_event,
            claim_owner="pub-1",
        )


@pytest.mark.asyncio
async def test_run_publisher_loop_graceful_shutdown():
    """Publisher polling loop exits cleanly when stop_event is triggered."""
    stop_event = asyncio.Event()
    stop_event.set()

    with patch("app.tasks.outbox_publisher.publish_pending_events", return_value=0) as mock_publish:
        await run_publisher_loop(poll_interval=0.01, stop_event=stop_event)
        mock_publish.assert_not_called()
