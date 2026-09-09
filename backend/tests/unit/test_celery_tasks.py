"""Unit tests for Celery task entrypoint."""

import uuid
from unittest.mock import patch

from app.tasks.jobs import process_job_task


def test_process_job_task_valid_uuid():
    """process_job_task parses valid UUID and calls executor."""
    test_id = str(uuid.uuid4())
    with patch("app.tasks.jobs.execute_job_by_id") as mock_exec:
        process_job_task(test_id)
        mock_exec.assert_called_once_with(uuid.UUID(test_id))


def test_process_job_task_invalid_uuid():
    """process_job_task handles invalid UUID safely without unhandled exceptions."""
    with patch("app.tasks.jobs.execute_job_by_id") as mock_exec:
        process_job_task("invalid-uuid-string")
        mock_exec.assert_not_called()
