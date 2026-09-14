"""Unit tests for Phase 11 structured job lifecycle logging, daemon loop sanitization, and error sanitization."""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.constants import JobStatus, OutboxStatus
from app.core.logging import sanitize_error
from app.models.job import Job
from app.models.outbox import OutboxEvent
from app.repositories.outbox import OutboxRepository
from app.tasks.executor import _execute_handler_and_settle
from app.tasks.job_recovery import run_recovery_loop
from app.tasks.outbox_publisher import run_publisher_loop


def test_sanitize_error_strips_database_and_rabbitmq_credentials():
    err1 = "Connection failed to postgresql+asyncpg://admin:supersecret123@db.prod.internal:5432/platform"
    assert sanitize_error(err1) == "Connection failed to postgresql+asyncpg://***:***@db.prod.internal:5432/platform"

    err2 = "Failed to publish message to amqp://guest:secretbrokerpass@rabbitmq.prod:5672//"
    assert sanitize_error(err2) == "Failed to publish message to amqp://***:***@rabbitmq.prod:5672//"


def test_sanitize_error_strips_redis_empty_user_and_http_credentials():
    # Empty username format for Redis: redis://:pass@host:port
    err_redis = "Redis auth failed at redis://:super_redis_pw@cache.prod:6379/0"
    assert sanitize_error(err_redis) == "Redis auth failed at redis://***:***@cache.prod:6379/0"

    err_http = "Proxy failed connecting to http://svc_user:svc_pass@proxy.corp:8080/path"
    assert sanitize_error(err_http) == "Proxy failed connecting to http://***:***@proxy.corp:8080/path"


def test_sanitize_error_strips_query_secrets_tokens_and_bearer_headers():
    # Query parameters
    err_query = "Request failed for https://example.com/api?token=secret_token_123&client_secret=topsecret"
    sanitized = sanitize_error(err_query)
    assert "secret_token_123" not in sanitized
    assert "topsecret" not in sanitized
    assert "token=***" in sanitized
    assert "client_secret=***" in sanitized

    # Query password & api_key
    err_pw = "Failed at /auth?password=mypassword999&api_key=apikey_xyz"
    sanitized_pw = sanitize_error(err_pw)
    assert "mypassword999" not in sanitized_pw
    assert "apikey_xyz" not in sanitized_pw
    assert "password=***" in sanitized_pw
    assert "api_key=***" in sanitized_pw

    # Authorization Bearer header
    err_bearer = "Unauthorized error: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature"
    sanitized_bearer = sanitize_error(err_bearer)
    assert "eyJ" not in sanitized_bearer
    assert "Bearer ***" in sanitized_bearer


def test_sanitize_error_preserves_clean_messages():
    clean_err = "Task timed out after 30 seconds while processing PDF report"
    assert sanitize_error(clean_err) == clean_err


@pytest.mark.asyncio
async def test_structured_logging_on_successful_execution():
    job_id = uuid.uuid4()
    claim_owner = "worker-test-1234"
    celery_task_id = "celery-task-abcd-5678"

    job = Job(
        id=job_id,
        project_id=uuid.uuid4(),
        job_type="REPORT_GENERATION",
        status=JobStatus.PROCESSING,
        payload={"type": "summary"},
    )

    mock_session = AsyncMock()
    mock_service = AsyncMock()
    mock_service.complete_job.return_value = job

    with patch("app.tasks.executor.logger") as mock_logger:
        await _execute_handler_and_settle(
            session=mock_session,
            job_service=mock_service,
            job=job,
            claim_owner=claim_owner,
            celery_task_id=celery_task_id,
        )

        assert mock_logger.info.call_count == 2
        calls = mock_logger.info.call_args_list
        event_names = [c[0][0] for c in calls]
        assert event_names == ["job_execution_started", "job_execution_completed"]

        started_kw = calls[0][1]
        assert started_kw["job_id"] == str(job_id)
        assert started_kw["job_type"] == "REPORT_GENERATION"
        assert started_kw["claim_owner"] == claim_owner
        assert started_kw["celery_task_id"] == celery_task_id

        completed_kw = calls[1][1]
        assert completed_kw["job_id"] == str(job_id)
        assert completed_kw["job_type"] == "REPORT_GENERATION"
        assert completed_kw["claim_owner"] == claim_owner
        assert completed_kw["celery_task_id"] == celery_task_id
        assert "duration_ms" in completed_kw


@pytest.mark.asyncio
async def test_structured_logging_on_stale_worker_rejection():
    job_id = uuid.uuid4()
    claim_owner = "stale-worker-9999"

    job = Job(
        id=job_id,
        project_id=uuid.uuid4(),
        job_type="REPORT_GENERATION",
        status=JobStatus.PROCESSING,
        payload={},
    )

    mock_session = AsyncMock()
    mock_service = AsyncMock()
    mock_service.complete_job.return_value = None  # Fencing rejection: ownership lost

    with patch("app.tasks.executor.logger") as mock_logger:
        await _execute_handler_and_settle(
            session=mock_session,
            job_service=mock_service,
            job=job,
            claim_owner=claim_owner,
            celery_task_id=None,
        )

        warning_calls = [call for call in mock_logger.warning.call_args_list if call[0][0] == "stale_worker_completion_rejected"]
        assert len(warning_calls) == 1
        kw = warning_calls[0][1]
        assert kw["job_id"] == str(job_id)
        assert kw["claim_owner"] == claim_owner
        assert kw["reason"] == "ownership_lost_or_lease_expired"


# ---------------------------------------------------------------------------
# Background Daemon Loop Exception Sanitization Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_outbox_publisher_loop_exception_sanitizes_credentials():
    """Prove that an exception in outer publisher loop containing credentials is sanitized before logging."""
    stop_event = asyncio.Event()

    sensitive_exception = ConnectionError(
        "Failed to connect to amqp://user_admin:super_secret_password_999@rabbitmq.prod:5672//?token=jwt_secret_token_123"
    )

    call_count = 0
    async def mock_publish(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        stop_event.set()  # Stop loop after one error
        raise sensitive_exception

    with patch("app.tasks.outbox_publisher.publish_pending_events", side_effect=mock_publish):
        with patch("app.tasks.outbox_publisher.logger") as mock_logger:
            await run_publisher_loop(
                poll_interval=0.01,
                stop_event=stop_event,
            )

            error_calls = [c for c in mock_logger.error.call_args_list if c[0][0] == "outbox_publisher_loop_error"]
            assert len(error_calls) >= 1
            logged_error = error_calls[0][1]["error"]

            # Verify credentials and tokens are redacted
            assert "super_secret_password_999" not in logged_error
            assert "jwt_secret_token_123" not in logged_error
            assert "amqp://***:***@rabbitmq.prod:5672//" in logged_error
            assert "token=***" in logged_error


@pytest.mark.asyncio
async def test_job_recovery_loop_exception_sanitizes_credentials():
    """Prove that an exception in outer recovery loop containing credentials is sanitized before logging."""
    stop_event = asyncio.Event()

    sensitive_exception = RuntimeError(
        "Redis cluster unreachable at redis://:redis_secret_auth_pass@redis:6379/0 and Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.secret"
    )

    call_count = 0
    async def mock_recover(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        stop_event.set()  # Stop loop after one error
        raise sensitive_exception

    with patch("app.tasks.job_recovery.recover_and_dispatch_jobs", side_effect=mock_recover):
        with patch("app.tasks.job_recovery.logger") as mock_logger:
            await run_recovery_loop(
                poll_interval=0.01,
                stop_event=stop_event,
            )

            error_calls = [c for c in mock_logger.error.call_args_list if c[0][0] == "job_recovery_loop_error"]
            assert len(error_calls) >= 1
            logged_error = error_calls[0][1]["error"]

            # Verify password and JWT are redacted
            assert "redis_secret_auth_pass" not in logged_error
            assert "eyJ" not in logged_error
            assert "redis://***:***@redis:6379/0" in logged_error
            assert "Bearer ***" in logged_error


@pytest.mark.asyncio
async def test_outbox_repository_record_failure_sanitizes_persisted_error():
    """Verify that OutboxRepository.record_failure passes last_error through sanitize_error."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    fake_event = OutboxEvent(
        id=uuid.uuid4(),
        aggregate_id=uuid.uuid4(),
        event_type="JOB_CREATED",
        payload={},
        status=OutboxStatus.CLAIMED,
        claim_owner="test-owner",
    )
    mock_result.scalar_one_or_none.return_value = fake_event
    mock_session.execute = AsyncMock(return_value=mock_result)

    repo = OutboxRepository(mock_session)
    unsanitized_error = "Broker failed: amqp://guest:secretbrokerpass@rabbitmq:5672//?client_secret=sensitive_client_secret_xyz"

    await repo.record_failure(
        event_id=fake_event.id,
        error_message=unsanitized_error,
        claim_owner="test-owner",
    )

    assert mock_session.execute.call_count == 1
    stmt = mock_session.execute.call_args[0][0]
    # Check the compiled/bound values in update statement
    params = stmt._values
    assert "last_error" in [col.key for col in params.keys()]
    for col, val in params.items():
        if col.key == "last_error":
            raw_val = getattr(val, "value", str(val))
            assert "secretbrokerpass" not in raw_val
            assert "sensitive_client_secret_xyz" not in raw_val
            assert "client_secret=***" in raw_val
