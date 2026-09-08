"""Authentication, JWT validation, and role extraction."""

from enum import StrEnum

import jwt
from jwt import PyJWKClient
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Configure a proper in-process cache for Keycloak's public keys.
# We set cache_jwk_set=True with lifespan=300 to cache the entire keyset
# for 5 minutes. We set cache_keys=False because it relies on an LRU cache
# without time-based expiration, which contradicts the lifespan TTL.
jwks_client = PyJWKClient(
    settings.keycloak_jwks_url,
    cache_keys=False,
    cache_jwk_set=True,
    lifespan=300
)


class Role(StrEnum):
    """Application roles managed via Keycloak realm roles."""

    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    MEMBER = "MEMBER"


def extract_roles(payload: dict) -> list[Role]:
    """
    Extract recognized application roles from a validated JWT payload.

    Keycloak places realm roles at payload["realm_access"]["roles"].
    Unrecognized roles (e.g. offline_access, uma_authorization) are ignored.
    Missing or malformed structures are handled gracefully.
    """
    try:
        realm_access = payload.get("realm_access")
        if not isinstance(realm_access, dict):
            return []
        raw_roles = realm_access.get("roles")
        if not isinstance(raw_roles, list):
            return []
        return [Role(r) for r in raw_roles if isinstance(r, str) and r in Role.__members__]
    except (ValueError, KeyError):
        return []


class AuthenticatedUser(BaseModel):
    """Typed representation of an authenticated identity."""

    sub: str
    preferred_username: str | None = None
    email: str | None = None
    name: str | None = None
    azp: str = Field(description="Authorized Party (Client ID)")
    roles: list[Role] = Field(default_factory=list, description="Application roles from realm_access")


def verify_jwt_token(token: str) -> AuthenticatedUser:
    """
    Validate the incoming Bearer token against Keycloak's public keys.
    Raises jwt exceptions (jwt.InvalidTokenError, jwt.ExpiredSignatureError, etc.) on failure.
    """
    try:
        # 1. Fetch the signing key from the JWKS endpoint (uses in-process cache)
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # 2. Decode and validate signature, expiration, issuer, and audience
        payload = jwt.decode(
            token,
            key=signing_key.key,
            algorithms=["RS256"],
            issuer=settings.keycloak_issuer,
            audience=settings.KEYCLOAK_CLIENT_ID
        )

        # 3. Validate Authorized Party (azp) matches our configured Client ID
        azp = payload.get("azp")
        if azp != settings.KEYCLOAK_CLIENT_ID:
            logger.warning("auth_azp_mismatch", expected=settings.KEYCLOAK_CLIENT_ID, received=azp)
            raise jwt.InvalidTokenError("Invalid authorized party (azp).")

        # 4. Extract application roles from the validated payload
        roles = extract_roles(payload)

        return AuthenticatedUser(**payload, roles=roles)

    except jwt.PyJWKClientError as e:
        logger.error("jwks_fetch_error", error=str(e))
        raise jwt.InvalidTokenError("Unable to fetch JWKS signing keys.")
