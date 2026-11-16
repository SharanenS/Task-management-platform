from types import SimpleNamespace

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from gateway.app import create_app as gateway_app
from people.app import create_app as people_app
from people.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from taskspace_security.settings import SecuritySettings
from test_access import ISSUER, provision

SETTINGS = SecuritySettings(ISSUER, ISSUER + "/protocol/openid-connect/certs", "s" * 43)


@pytest.fixture
def boundary(monkeypatch):
    monkeypatch.setenv("AUTH_ALLOW_LOCAL_HTTP", "true")
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    with sessions() as s:
        identity = provision(s)

    def verify(token):
        if token != "valid-provider-token":
            raise jwt.InvalidTokenError()
        return identity

    verifier = SimpleNamespace(verify=verify)
    people = people_app(SETTINGS, sessions, verifier)
    gateway = gateway_app(SETTINGS, verifier, httpx.ASGITransport(app=people))
    yield TestClient(people), TestClient(gateway), sessions, identity
    engine.dispose()


def test_private_service_requires_both_service_and_identity_credentials(boundary):
    people, gateway, sessions, identity = boundary
    for headers in (
        {},
        {"X-Service-Key": SETTINGS.service_key},
        {"Authorization": "Bearer valid-provider-token"},
        {"X-Service-Key": SETTINGS.service_key, "Authorization": "Bearer forged"},
    ):
        assert people.get("/internal/actor", headers=headers).status_code == 401
    assert (
        people.get(
            "/internal/actor",
            headers={
                "X-Service-Key": SETTINGS.service_key,
                "Authorization": "Bearer valid-provider-token",
            },
        ).status_code
        == 200
    )


def test_graphql_validates_identity_and_ignores_client_actor_headers(boundary):
    people, gateway, sessions, identity = boundary
    query = {"query": "{ viewer { accountId employeeId companyRoles permissions } }"}
    for headers in ({}, {"Authorization": "Bearer forged", "X-Actor-Role": "ADMIN"}):
        assert gateway.post("/graphql", json=query, headers=headers).status_code == 401
    result = gateway.post(
        "/graphql",
        json=query,
        headers={
            "Authorization": "Bearer valid-provider-token",
            "X-Actor-Role": "ADMIN",
            "X-Actor-Id": "someone-else",
        },
    )
    assert result.status_code == 200
    assert result.json()["data"]["viewer"]["companyRoles"] == ["EMPLOYEE"]
    assert result.json()["data"]["viewer"]["permissions"] == ["account:self:read"]
    assert result.headers["Cache-Control"] == "no-store"


def test_existing_token_loses_access_after_profile_is_deactivated(boundary):
    from people.models import Account
    from sqlalchemy import select

    people, gateway, sessions, identity = boundary
    with sessions() as s:
        account = s.scalar(select(Account).where(Account.subject == identity.subject))
        account.profile.active = False
        s.commit()
    result = gateway.post(
        "/graphql",
        json={"query": "{ viewer { accountId } }"},
        headers={"Authorization": "Bearer valid-provider-token"},
    )
    assert result.status_code == 403
    assert "accountId" not in result.text


def test_people_outage_fails_closed(monkeypatch, boundary):
    people, gateway, sessions, identity = boundary

    def failure(request):
        raise httpx.ConnectError("private upstream failure")

    app = gateway_app(
        SETTINGS, SimpleNamespace(verify=lambda token: identity), httpx.MockTransport(failure)
    )
    result = TestClient(app).post(
        "/graphql",
        json={"query": "{ viewer { accountId } }"},
        headers={"Authorization": "Bearer valid-provider-token"},
    )
    assert result.status_code == 503
    assert "private upstream" not in result.text
