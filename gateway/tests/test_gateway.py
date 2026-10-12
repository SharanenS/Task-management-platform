import asyncio
from pathlib import Path

import httpx
import pytest

from app.main import app
from app.schema import schema


def request(
    method: str,
    path: str,
    *,
    payload: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, path, json=payload, params=params)

    return asyncio.run(send())


def test_system_info_contract() -> None:
    response = request(
        "POST",
        "/graphql",
        payload={
            "query": """
      query SystemInfo { systemInfo { name version environment status } }
    """
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["systemInfo"] == {
        "name": "Enterprise Task Platform Gateway",
        "version": "0.1.0",
        "environment": "development",
        "status": "AVAILABLE",
    }
    assert response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("path,status", [("/health/live", "alive"), ("/health/ready", "ready")])
def test_health(path: str, status: str) -> None:
    assert request("GET", path).json() == {"status": status}


def test_schema_export_matches_runtime() -> None:
    assert Path("schema.graphql").read_text(encoding="utf-8") == schema.as_str() + "\n"


def test_invalid_queries_are_sanitized() -> None:
    result = request("POST", "/graphql", payload={"query": "{ employees { password } }"}).json()
    assert result["errors"] == [{"message": "Invalid GraphQL request."}]
    assert result.get("data") is None


def test_alias_abuse_is_rejected() -> None:
    fields = " ".join(f"a{i}: systemInfo {{ status }}" for i in range(11))
    result = request("POST", "/graphql", payload={"query": "{" + fields + "}"}).json()
    assert result["errors"]
    assert result.get("data") is None


def test_get_queries_are_disabled() -> None:
    response = request("GET", "/graphql", params={"query": "{ systemInfo { status } }"})
    assert response.status_code == 400
