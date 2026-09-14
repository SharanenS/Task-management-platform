"""Tests for Phase 11 health endpoints (liveness & readiness)."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_liveness_live_endpoint(client):
    """Liveness probe at /api/v1/health/live returns 200 alive."""
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "version" in data


@pytest.mark.asyncio
async def test_liveness_legacy_endpoint(client):
    """Legacy liveness endpoint at /api/v1/health/liveness remains backward-compatible."""
    response = await client.get("/api/v1/health/liveness")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "version" in data


@pytest.mark.asyncio
@patch("app.api.v1.health.engine")
async def test_liveness_does_not_probe_database(mock_engine, client):
    """Liveness probe must be ultra-lightweight and NOT touch PostgreSQL."""
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    mock_engine.connect.assert_not_called()


@pytest.mark.asyncio
@patch("app.api.v1.health.engine")
async def test_readiness_ready_endpoint_success(mock_engine, client):
    """Readiness probe returns 200 and available status when DB is reachable."""
    mock_conn = AsyncMock()
    mock_engine.connect.return_value.__aenter__.return_value = mock_conn

    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "available"


@pytest.mark.asyncio
@patch("app.api.v1.health.engine")
async def test_readiness_legacy_endpoint_success(mock_engine, client):
    """Legacy readiness endpoint /api/v1/health/readiness remains backward-compatible."""
    mock_conn = AsyncMock()
    mock_engine.connect.return_value.__aenter__.return_value = mock_conn

    response = await client.get("/api/v1/health/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"


@pytest.mark.asyncio
@patch("app.api.v1.health.engine")
async def test_readiness_database_failure(mock_engine, client):
    """Readiness probe returns 503 when required PostgreSQL dependency fails."""
    mock_engine.connect.side_effect = Exception("FATAL: connection to server failed")

    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert data["checks"]["database"] == "unavailable"


@pytest.mark.asyncio
@patch("app.api.v1.health.engine")
async def test_health_endpoints_unauthenticated(mock_engine, client):
    """Health endpoints are unauthenticated (no Bearer token required)."""
    mock_conn = AsyncMock()
    mock_engine.connect.return_value.__aenter__.return_value = mock_conn

    res_live = await client.get("/api/v1/health/live")
    assert res_live.status_code == 200

    res_ready = await client.get("/api/v1/health/ready")
    assert res_ready.status_code == 200


@pytest.mark.asyncio
@patch("app.api.v1.health.engine")
async def test_health_endpoints_no_secret_leakage(mock_engine, client):
    """Health responses must never expose connection strings, passwords, or tokens."""
    mock_engine.connect.side_effect = Exception("postgresql://user:secretpass@host:5432/db")

    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 503
    body = response.text
    assert "secretpass" not in body
    assert "postgresql://" not in body
    assert "user:" not in body


@pytest.mark.asyncio
@patch("app.api.v1.health.engine")
async def test_liveness_succeeds_during_db_outage(mock_engine, client):
    """Liveness probe must return 200 OK even if database is completely offline/failing."""
    mock_engine.connect.side_effect = Exception("FATAL: Database crashed or network split")

    # Liveness probe must still succeed without error
    res_live = await client.get("/api/v1/health/live")
    assert res_live.status_code == 200
    assert res_live.json()["status"] == "alive"

    # In contrast, readiness MUST fail with 503 during the same DB outage
    res_ready = await client.get("/api/v1/health/ready")
    assert res_ready.status_code == 503
    assert res_ready.json()["status"] == "error"
