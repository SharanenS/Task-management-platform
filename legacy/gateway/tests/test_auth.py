from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth import AuthenticationError, TokenValidator
from app.config import settings


@pytest.fixture
def validator_and_key() -> tuple[TokenValidator, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    validator = TokenValidator()
    validator._jwks = SimpleNamespace(  # type: ignore[assignment]
        get_signing_key_from_jwt=lambda _: SimpleNamespace(key=key.public_key())
    )
    return validator, key


def token(key: rsa.RSAPrivateKey, **overrides: object) -> str:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "sub": "subject-1",
        "iss": settings.oidc_issuer,
        "aud": settings.oidc_audience,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})


def test_valid_token_returns_stable_subject(
    validator_and_key: tuple[TokenValidator, rsa.RSAPrivateKey],
) -> None:
    validator, key = validator_and_key
    assert validator.validate(f"Bearer {token(key)}").subject == "subject-1"


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://wrong.example/realms/taskspace"},
        {"aud": "wrong-client"},
        {"exp": datetime.now(UTC) - timedelta(seconds=1)},
    ],
)
def test_invalid_claims_are_rejected(
    validator_and_key: tuple[TokenValidator, rsa.RSAPrivateKey], overrides: dict[str, object]
) -> None:
    validator, key = validator_and_key
    with pytest.raises(AuthenticationError):
        validator.validate(f"Bearer {token(key, **overrides)}")


def test_malformed_token_is_rejected(
    validator_and_key: tuple[TokenValidator, rsa.RSAPrivateKey],
) -> None:
    validator, _ = validator_and_key
    with pytest.raises(AuthenticationError):
        validator.validate("Bearer malformed")
