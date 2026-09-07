"""Test health endpoint."""

import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.exc import OperationalError

@pytest.mark.asyncio
async def test_liveness_endpoint(client):
    """Liveness endpoint should return status alive."""
    response = await client.get("/api/v1/health/liveness")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "version" in data

@pytest.mark.asyncio
@patch("app.api.v1.health.engine")
async def test_readiness_endpoint_success(mock_engine, client):
    """Readiness endpoint returns 200 when DB is reachable."""
    mock_conn = AsyncMock()
    mock_engine.connect.return_value.__aenter__.return_value = mock_conn
    response = await client.get("/api/v1/health/readiness")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}

@pytest.mark.asyncio
@patch("app.api.v1.health.engine")
async def test_readiness_endpoint_failure(mock_engine, client):
    """Readiness endpoint returns 503 when DB is unreachable."""
    mock_engine.connect.side_effect = Exception("DB Connection Failed")
    response = await client.get("/api/v1/health/readiness")
    assert response.status_code == 503
    assert response.json() == {"status": "error"}