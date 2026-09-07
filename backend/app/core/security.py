"""Authentication and JWT validation security mechanisms."""

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


class AuthenticatedUser(BaseModel):
    """Typed representation of an authenticated identity."""

    sub: str
    preferred_username: str | None = None
    email: str | None = None
    name: str | None = None
    azp: str = Field(description="Authorized Party (Client ID)")


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
            
        return AuthenticatedUser(**payload)
        
    except jwt.PyJWKClientError as e:
        logger.error("jwks_fetch_error", error=str(e))
        raise jwt.InvalidTokenError("Unable to fetch JWKS signing keys.")