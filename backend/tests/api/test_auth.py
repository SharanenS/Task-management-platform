"""Tests for JWT authentication boundary."""

from unittest.mock import patch, MagicMock, call
import jwt
import pytest
from app.core.config import settings
from app.core.security import AuthenticatedUser, verify_jwt_token

@pytest.fixture
def valid_token_payload():
    return {
        "sub": "user-123",
        "preferred_username": "testuser",
        "email": "testuser@enterprise.local",
        "name": "Test User",
        "azp": settings.KEYCLOAK_CLIENT_ID,
        "iss": settings.keycloak_issuer,
        "aud": settings.KEYCLOAK_CLIENT_ID,
        "exp": 9999999999
    }

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
async def test_auth_me_valid_token(mock_decode, mock_get_key, client, valid_token_payload):
    """Valid token should return authenticated identity."""
    mock_get_key.return_value = MagicMock(key="mock-key")
    mock_decode.return_value = valid_token_payload

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer valid.token.here"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["sub"] == "user-123"
    assert data["azp"] == settings.KEYCLOAK_CLIENT_ID

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
async def test_auth_me_invalid_azp(mock_decode, mock_get_key, client, valid_token_payload):
    """Valid token with wrong azp should return 401."""
    mock_get_key.return_value = MagicMock(key="mock-key")
    
    bad_payload = valid_token_payload.copy()
    bad_payload["azp"] = "wrong-client-id"
    mock_decode.return_value = bad_payload

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer valid.token.wrong_azp"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"

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
    
    # Mocking urlopen to return a valid HTTP response with a dummy getheader
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
    
    # Reset mock_response stream for the next possible read if needed
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