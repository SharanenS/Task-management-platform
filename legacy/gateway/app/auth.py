from dataclasses import dataclass

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

from app.config import settings


class AuthenticationError(Exception):
    pass


@dataclass(frozen=True)
class Identity:
    subject: str


class TokenValidator:
    def __init__(self) -> None:
        self._jwks = PyJWKClient(
            settings.oidc_jwks_url,
            cache_jwk_set=True,
            lifespan=300,
            cache_keys=True,
            max_cached_keys=16,
        )

    def validate(self, authorization: str | None) -> Identity:
        if not authorization or not authorization.startswith("Bearer "):
            raise AuthenticationError
        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            raise AuthenticationError
        try:
            key = self._jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                audience=settings.oidc_audience,
                issuer=settings.oidc_issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except (InvalidTokenError, jwt.PyJWKClientError) as error:
            raise AuthenticationError from error
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise AuthenticationError
        return Identity(subject=subject)


token_validator = TokenValidator()
