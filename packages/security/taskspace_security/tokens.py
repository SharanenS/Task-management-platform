"""Validate provider identity; application roles are deliberately not token claims."""

from dataclasses import dataclass
from urllib.parse import urlsplit

import jwt
from jwt import PyJWKClient


@dataclass(frozen=True)
class Identity:
    issuer: str
    subject: str


class TokenVerifier:
    def __init__(self, issuer: str, jwks_url: str, audience: str, client_id: str):
        parsed = urlsplit(issuer)
        keys = urlsplit(jwks_url)
        if (
            parsed.scheme not in {"https", "http"}
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
            or not parsed.netloc
            or keys.query
            or keys.fragment
            or keys.username
            or keys.password
        ):
            raise ValueError("Invalid identity boundary")
        self.issuer = issuer
        self.audience = audience
        self.client_id = client_id
        self.keys = PyJWKClient(jwks_url, cache_keys=False, lifespan=30, timeout=5)

    def verify(self, token: str) -> Identity:
        if not token or len(token) > 16384:
            raise jwt.InvalidTokenError("Invalid bearer credential")
        key = self.keys.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=self.issuer,
            audience=self.audience,
            options={"require": ["exp", "iat", "iss", "aud", "sub", "azp", "typ"]},
        )
        if (
            claims["azp"] != self.client_id
            or claims["typ"] != "Bearer"
            or not isinstance(claims["sub"], str)
            or not claims["sub"]
            or len(claims["sub"]) > 255
        ):
            raise jwt.InvalidTokenError("Invalid identity claims")
        return Identity(self.issuer, claims["sub"])
