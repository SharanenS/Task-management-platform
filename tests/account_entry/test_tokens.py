from datetime import datetime, timezone
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from taskspace_security.tokens import TokenVerifier

ISSUER = "https://identity.example/realms/taskspace-portals"


@pytest.fixture
def signed():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = TokenVerifier(
        ISSUER,
        ISSUER + "/protocol/openid-connect/certs",
        "taskspace-portals-api",
        "taskspace-portals-web",
    )
    verifier.keys = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key())
    )
    now = int(datetime.now(timezone.utc).timestamp())
    claims = {
        "iss": ISSUER,
        "sub": "person",
        "aud": "taskspace-portals-api",
        "azp": "taskspace-portals-web",
        "typ": "Bearer",
        "iat": now,
        "exp": now + 60,
    }
    return key, verifier, claims


def test_verified_identity_does_not_inherit_token_roles(signed):
    key, verifier, claims = signed
    claims["realm_access"] = {"roles": ["ADMIN"]}
    identity = verifier.verify(jwt.encode(claims, key, algorithm="RS256"))
    assert identity.subject == "person"
    assert not hasattr(identity, "roles")


@pytest.mark.parametrize(
    "field,value",
    [
        ("iss", "https://other.example"),
        ("aud", "other-api"),
        ("azp", "other-client"),
        ("typ", "ID"),
        ("exp", 1),
        ("sub", ""),
        ("iat", 9999999999),
    ],
)
def test_invalid_provider_claim_is_denied(signed, field, value):
    key, verifier, claims = signed
    claims[field] = value
    with pytest.raises(jwt.InvalidTokenError):
        verifier.verify(jwt.encode(claims, key, algorithm="RS256"))


def test_wrong_signature_and_unsigned_token_are_denied(signed):
    key, verifier, claims = signed
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    for token in (
        jwt.encode(claims, other, algorithm="RS256"),
        jwt.encode(claims, "", algorithm="none"),
    ):
        with pytest.raises(jwt.InvalidTokenError):
            verifier.verify(token)
