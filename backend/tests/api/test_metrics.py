"""Tests for Phase 11 operational metrics and Prometheus exposition."""

import pytest
from unittest.mock import AsyncMock, patch

from app.core.metrics import MetricsRegistry, metrics


def test_metrics_registry_recording_and_bounded_labels():
    """Verify registry increments counters and records histograms with safe bounded labels."""
    reg = MetricsRegistry()

    reg.record_job_execution("REPORT_GENERATION", "success", 0.125)
    reg.record_job_execution("REPORT_GENERATION", "failure", 0.450, error_type="ValueError")
    reg.record_job_recovery(count=3)
    reg.record_outbox_published(0.015)
    reg.record_outbox_failure()
    reg.record_http_request("GET", 200, 0.020)

    # Validate in-memory counter states
    assert reg._counters["job_executions_total"][(("job_type", "REPORT_GENERATION"), ("outcome", "success"))] == 1.0
    assert reg._counters["job_executions_total"][(("job_type", "REPORT_GENERATION"), ("outcome", "failure"))] == 1.0
    assert reg._counters["job_execution_failures_total"][(("error_type", "ValueError"), ("job_type", "REPORT_GENERATION"))] == 1.0
    assert reg._counters["jobs_recovered_total"][()] == 3.0
    assert reg._counters["outbox_published_total"][()] == 1.0
    assert reg._counters["outbox_failures_total"][()] == 1.0
    assert reg._counters["http_requests_total"][(("method", "GET"), ("status", "200"))] == 1.0


@pytest.mark.asyncio
async def test_prometheus_text_format_generation():
    """Verify generated text matches standard Prometheus exposition format."""
    reg = MetricsRegistry()
    reg.record_job_recovery(5)
    reg.record_job_execution("REPORT_GENERATION", "success", 0.05)

    text_output = await reg.generate_prometheus_text(session=None)

    assert "# HELP jobs_recovered_total" in text_output
    assert "# TYPE jobs_recovered_total counter" in text_output
    assert "jobs_recovered_total 5" in text_output

    assert "# HELP job_executions_total" in text_output
    assert "# TYPE job_executions_total counter" in text_output
    assert 'job_executions_total{job_type="REPORT_GENERATION",outcome="success"} 1' in text_output

    assert "# TYPE job_execution_duration_seconds histogram" in text_output
    assert "job_execution_duration_seconds_count" in text_output
    assert "job_execution_duration_seconds_sum" in text_output


@pytest.mark.asyncio
async def test_metrics_api_endpoint_v1(client):
    """GET /api/v1/metrics returns 200 and Prometheus content-type."""
    response = await client.get("/api/v1/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    text = response.text

    # Operational metrics must be present
    for metric_name in [
        "jobs_queued",
        "jobs_processing",
        "jobs_completed",
        "jobs_failed",
        "jobs_expired",
        "outbox_pending",
        "outbox_failures",
    ]:
        assert f"# TYPE {metric_name} gauge" in text or metric_name in text


@pytest.mark.asyncio
async def test_metrics_api_root_endpoint(client):
    """Standard Prometheus scraper at /metrics returns 200."""
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_metrics_no_sensitive_labels_or_secrets(client):
    """Metrics output must never expose high-cardinality IDs, passwords, or tokens."""
    response = await client.get("/api/v1/metrics")
    text = response.text

    # Verify no raw sensitive keys or high-cardinality label keys
    assert "password" not in text.lower()
    assert "secret" not in text.lower()
    assert "jwt" not in text.lower()
    assert "token" not in text.lower()
    assert "celery_task_id" not in text
    assert "claim_owner" not in text


def test_prometheus_label_escaping():
    """Verify that quotes and backslashes in label values are properly escaped."""
    reg = MetricsRegistry()
    reg.increment_counter("test_escaping_total", 1.0, {"error": 'Failed with "bad_quotes" and \\slash'})

    rendered = reg._format_labels({"error": 'Failed with "bad_quotes" and \\slash'})
    assert '\\"bad_quotes\\"' in rendered
    assert '\\\\slash' in rendered


@pytest.mark.asyncio
async def test_http_requests_total_bounded_cardinality(client):
    """Verify that http_requests_total labels are strictly bounded (method and status only) and do not leak user paths or UUIDs."""
    uuid1 = "123e4567-e89b-12d3-a456-426614174000"
    uuid2 = "987f6543-e21b-34c5-d678-123456789abc"

    await client.get(f"/api/v1/jobs/{uuid1}")
    await client.get(f"/api/v1/projects/{uuid2}")

    response = await client.get("/metrics")
    metrics_text = response.text

    # Metrics text must NEVER contain raw user path UUIDs
    assert uuid1 not in metrics_text
    assert uuid2 not in metrics_text

    # Series for http_requests_total only has method and status
    for line in metrics_text.splitlines():
        if line.startswith("http_requests_total{"):
            assert "method=" in line
            assert "status=" in line
            assert "path=" not in line
