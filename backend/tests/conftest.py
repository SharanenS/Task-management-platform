"""Shared test fixtures."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import engine
from app.main import app


@pytest.fixture(autouse=True)
async def cleanup_engine():
    """Ensure connections attached to a closed event loop do not leak into subsequent tests."""
    yield
    await engine.dispose()


@pytest.fixture
async def client():
    """Async HTTP test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as ac:
        yield ac
