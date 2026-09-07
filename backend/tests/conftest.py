"""Shared test fixtures."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

@pytest.fixture
async def client():
    """Async HTTP test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as ac:
        yield ac