"""Test health endpoint."""

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Health endpoint should return status and version."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data