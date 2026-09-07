"""Test exception handling."""

import pytest
from fastapi import APIRouter
from app.core.exceptions import AppException
from app.main import app

exception_router = APIRouter()

@exception_router.get("/api/v1/test-exception")
async def raise_exception():
    raise AppException(status_code=400, detail="Bad Request Error")

@exception_router.get("/api/v1/test-internal-error")
async def raise_internal_error():
    raise Exception("Secret Database Failure 12345")

app.include_router(exception_router)

@pytest.mark.asyncio
async def test_app_exception_handler(client):
    """Test custom AppException produces correct JSON response."""
    response = await client.get("/api/v1/test-exception")
    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "Bad Request Error"

@pytest.mark.asyncio
async def test_internal_server_error_handler(client):
    """Test unhandled exceptions do not leak stack traces."""
    response = await client.get("/api/v1/test-internal-error")
    assert response.status_code == 500
    assert "Secret Database Failure" not in response.text