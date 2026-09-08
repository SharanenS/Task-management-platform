"""Tests for JWT authentication and role-based authorization."""

from unittest.mock import patch, MagicMock
import jwt
import pytest
from app.core.config import settings
from app.core.security import AuthenticatedUser, Role, extract_roles, verify_jwt_token


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def base_payload():
    """Minimal valid JWT payload without roles."""
    return {
        "sub": "user-123",
        "preferred_username": "testuser",
        "email": "testuser@enterprise.local",
        "name": "Test User",
        "azp": settings.KEYCLOAK_CLIENT_ID,
        "iss": settings.keycloak_issuer,
        "aud": settings.KEYCLOAK_CLIENT_ID,
        "exp": 9999999999,
    }


def _payload_with_roles(base, roles):
    """Return a copy of base payload with realm_access.roles set."""
    p = base.copy()
    p["realm_access"] = {"roles": roles}
    return p


# ── Phase 2 Authentication Tests (preserved) ────────────────────────────────

@pytest.mark.asyncio
async def test_auth_me_missing_token(client):
    """Missing bearer token should return 401."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.asyncio
async def test_auth_me_malformed_token(client):
    """Malformed bearer token should return 401."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer malformed"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_auth_me_valid_token(mock_decode, mock_get_key, client, base_payload):
    """Valid token should return authenticated identity with roles."""
    mock_get_key.return_value = MagicMock(key="mock-key")
    mock_decode.return_value = _payload_with_roles(base_payload, ["ADMIN"])

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer valid.token.here"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sub"] == "user-123"
    assert data["azp"] == settings.KEYCLOAK_CLIENT_ID
    assert data["roles"] == ["ADMIN"]


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
async def test_auth_me_expired_token(mock_get_key, client):
    """Expired token should return 401."""
    mock_get_key.return_value = MagicMock(key="mock-key")

    with patch("app.core.security.jwt.decode", side_effect=jwt.ExpiredSignatureError):
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer expired.token.here"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Token has expired"


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
async def test_auth_me_invalid_signature(mock_get_key, client):
    """Invalid signature should return 401."""
    mock_get_key.return_value = MagicMock(key="mock-key")

    with patch("app.core.security.jwt.decode", side_effect=jwt.InvalidSignatureError):
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.signature.here"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Could not validate credentials"


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
async def test_auth_me_wrong_issuer(mock_get_key, client):
    """Wrong issuer should return 401."""
    mock_get_key.return_value = MagicMock(key="mock-key")

    with patch("app.core.security.jwt.decode", side_effect=jwt.InvalidIssuerError):
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer wrong.issuer.here"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Could not validate credentials"


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
async def test_auth_me_wrong_audience(mock_get_key, client):
    """Wrong audience should return 401."""
    mock_get_key.return_value = MagicMock(key="mock-key")

    with patch("app.core.security.jwt.decode", side_effect=jwt.InvalidAudienceError):
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer wrong.audience.here"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Could not validate credentials"


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_auth_me_invalid_azp(mock_decode, mock_get_key, client, base_payload):
    """Valid token with wrong azp should return 401."""
    mock_get_key.return_value = MagicMock(key="mock-key")

    bad_payload = base_payload.copy()
    bad_payload["azp"] = "wrong-client-id"
    mock_decode.return_value = bad_payload

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer valid.token.wrong_azp"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


# ── Phase 2 JWKS Caching Test (preserved) ───────────────────────────────────

@patch("jwt.jwks_client.urllib.request.urlopen")
def test_jwks_caching(mock_urlopen):
    """Verify PyJWKClient cache behavior."""
    from jwt import PyJWKClient
    import io
    import json

    test_client = PyJWKClient(
        "http://dummy/certs",
        cache_keys=False,
        cache_jwk_set=True,
        lifespan=300
    )

    mock_response = io.BytesIO(json.dumps({
        "keys": [{
            "kid": "key1",
            "kty": "RSA",
            "alg": "RS256",
            "use": "sig",
            "n": "u18G_Lh2mGg-vFqj7hE1_7u5m3w6qP_X1Kx2",
            "e": "AQAB"
        },
        {
            "kid": "key2",
            "kty": "RSA",
            "alg": "RS256",
            "use": "sig",
            "n": "u18G_Lh2mGg-vFqj7hE1_7u5m3w6qP_X1Kx2",
            "e": "AQAB"
        }]
    }).encode("utf-8"))

    class MockResponse:
        def __init__(self, f):
            self.f = f
        def read(self):
            return self.f.read()
        def getheader(self, name, default=None):
            return "max-age=300" if name.lower() == "cache-control" else default
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    mock_urlopen.return_value = MockResponse(mock_response)

    dummy_token_1 = "eyJhbGciOiAiUlMyNTYiLCAia2lkIjogImtleTEifQ.e30.dummyyyy"

    test_client.get_signing_key_from_jwt(dummy_token_1)

    mock_response.seek(0)

    test_client.get_signing_key_from_jwt(dummy_token_1)

    assert mock_urlopen.call_count == 1

    mock_response.seek(0)

    dummy_token_2 = "eyJhbGciOiAiUlMyNTYiLCAia2lkIjogImtleTIifQ.e30.dummyyyy"
    test_client.get_signing_key_from_jwt(dummy_token_2)

    assert mock_urlopen.call_count == 1

    dummy_token_3 = "eyJhbGciOiAiUlMyNTYiLCAia2lkIjogImtleTMifQ.e30.dummyyyy"
    try:
        test_client.get_signing_key_from_jwt(dummy_token_3)
    except Exception:
        pass

    assert mock_urlopen.call_count == 2


# ── Phase 3 Role Extraction Unit Tests ──────────────────────────────────────

def test_extract_roles_with_valid_roles():
    """Token with realm_access.roles extracts recognized application roles."""
    payload = {"realm_access": {"roles": ["ADMIN", "MEMBER"]}}
    roles = extract_roles(payload)
    assert roles == [Role.ADMIN, Role.MEMBER]


def test_extract_roles_ignores_unrecognized():
    """Unrelated Keycloak roles (offline_access, uma_authorization) are ignored."""
    payload = {"realm_access": {"roles": ["ADMIN", "offline_access", "uma_authorization"]}}
    roles = extract_roles(payload)
    assert roles == [Role.ADMIN]


def test_extract_roles_missing_realm_access():
    """Missing realm_access returns empty list, no crash."""
    payload = {"sub": "user-1"}
    roles = extract_roles(payload)
    assert roles == []


def test_extract_roles_missing_roles_key():
    """realm_access without roles key returns empty list."""
    payload = {"realm_access": {}}
    roles = extract_roles(payload)
    assert roles == []


def test_extract_roles_realm_access_not_dict():
    """realm_access as non-dict returns empty list."""
    payload = {"realm_access": "invalid"}
    roles = extract_roles(payload)
    assert roles == []


def test_extract_roles_roles_not_list():
    """realm_access.roles as non-list returns empty list."""
    payload = {"realm_access": {"roles": "ADMIN"}}
    roles = extract_roles(payload)
    assert roles == []


def test_extract_roles_non_string_entries():
    """Non-string entries in roles list are ignored."""
    payload = {"realm_access": {"roles": ["ADMIN", 123, None, "MEMBER"]}}
    roles = extract_roles(payload)
    assert roles == [Role.ADMIN, Role.MEMBER]


# ── Phase 3 Authorization Endpoint Tests ────────────────────────────────────

@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_admin_endpoint_admin_allowed(mock_decode, mock_get_key, client, base_payload):
    """ADMIN accessing /admin -> 200."""
    mock_get_key.return_value = MagicMock(key="mock-key")
    mock_decode.return_value = _payload_with_roles(base_payload, ["ADMIN"])

    response = await client.get(
        "/api/v1/auth/admin",
        headers={"Authorization": "Bearer valid.admin.token"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Admin area"


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_admin_endpoint_manager_forbidden(mock_decode, mock_get_key, client, base_payload):
    """MANAGER accessing /admin -> 403."""
    mock_get_key.return_value = MagicMock(key="mock-key")
    mock_decode.return_value = _payload_with_roles(base_payload, ["MANAGER"])

    response = await client.get(
        "/api/v1/auth/admin",
        headers={"Authorization": "Bearer valid.manager.token"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_admin_endpoint_member_forbidden(mock_decode, mock_get_key, client, base_payload):
    """MEMBER accessing /admin -> 403."""
    mock_get_key.return_value = MagicMock(key="mock-key")
    mock_decode.return_value = _payload_with_roles(base_payload, ["MEMBER"])

    response = await client.get(
        "/api/v1/auth/admin",
        headers={"Authorization": "Bearer valid.member.token"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_management_endpoint_admin_allowed(mock_decode, mock_get_key, client, base_payload):
    """ADMIN accessing /management -> 200."""
    mock_get_key.return_value = MagicMock(key="mock-key")
    mock_decode.return_value = _payload_with_roles(base_payload, ["ADMIN"])

    response = await client.get(
        "/api/v1/auth/management",
        headers={"Authorization": "Bearer valid.admin.token"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Management area"


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_management_endpoint_manager_allowed(mock_decode, mock_get_key, client, base_payload):
    """MANAGER accessing /management -> 200."""
    mock_get_key.return_value = MagicMock(key="mock-key")
    mock_decode.return_value = _payload_with_roles(base_payload, ["MANAGER"])

    response = await client.get(
        "/api/v1/auth/management",
        headers={"Authorization": "Bearer valid.manager.token"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Management area"


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_management_endpoint_member_forbidden(mock_decode, mock_get_key, client, base_payload):
    """MEMBER accessing /management -> 403."""
    mock_get_key.return_value = MagicMock(key="mock-key")
    mock_decode.return_value = _payload_with_roles(base_payload, ["MEMBER"])

    response = await client.get(
        "/api/v1/auth/management",
        headers={"Authorization": "Bearer valid.member.token"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_member_endpoint_member_allowed(mock_decode, mock_get_key, client, base_payload):
    """MEMBER accessing /member-area -> 200."""
    mock_get_key.return_value = MagicMock(key="mock-key")
    mock_decode.return_value = _payload_with_roles(base_payload, ["MEMBER"])

    response = await client.get(
        "/api/v1/auth/member-area",
        headers={"Authorization": "Bearer valid.member.token"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Member area"


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_member_endpoint_admin_forbidden(mock_decode, mock_get_key, client, base_payload):
    """ADMIN accessing /member-area -> 403 (ADMIN does not have MEMBER role)."""
    mock_get_key.return_value = MagicMock(key="mock-key")
    mock_decode.return_value = _payload_with_roles(base_payload, ["ADMIN"])

    response = await client.get(
        "/api/v1/auth/member-area",
        headers={"Authorization": "Bearer valid.admin.token"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


@pytest.mark.asyncio
async def test_admin_endpoint_missing_token(client):
    """Missing token on role-protected endpoint -> 401 not 403."""
    response = await client.get("/api/v1/auth/admin")
    assert response.status_code == 401


@pytest.mark.asyncio
@patch("app.core.security.jwks_client.get_signing_key_from_jwt")
@patch("app.core.security.jwt.decode")
async def test_admin_endpoint_no_roles(mock_decode, mock_get_key, client, base_payload):
    """Authenticated user with no roles -> 403."""
    mock_get_key.return_value = MagicMock(key="mock-key")
    mock_decode.return_value = base_payload  # no realm_access

    response = await client.get(
        "/api/v1/auth/admin",
        headers={"Authorization": "Bearer valid.noroles.token"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"
