"""Security utilities: JWT validation, password hashing, Keycloak integration."""

from datetime import datetime, timedelta, timezone

import httpx
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.logging import get_logger

logger = get_logger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Cached Keycloak JWKS
_jwks_cache: dict | None = None


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


async def get_keycloak_jwks() -> dict:
    """Fetch the JWKS from Keycloak for token verification."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    jwks_url = (
        f"{settings.KEYCLOAK_SERVER_URL}/realms/{settings.KEYCLOAK_REALM}"
        f"/protocol/openid-connect/certs"
    )
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(jwks_url, timeout=10.0)
            response.raise_for_status()
            _jwks_cache = response.json()
            return _jwks_cache
        except httpx.HTTPError as e:
            logger.warning("keycloak_jwks_fetch_failed", error=str(e))
            raise UnauthorizedError("Authentication service unavailable")


async def decode_keycloak_token(token: str) -> dict:
    """Decode and validate a Keycloak-issued JWT."""
    try:
        jwks = await get_keycloak_jwks()
        unverified_header = jwt.get_unverified_header(token)

        rsa_key = {}
        for key in jwks.get("keys", []):
            if key["kid"] == unverified_header.get("kid"):
                rsa_key = key
                break

        if not rsa_key:
            raise UnauthorizedError("Invalid token signing key")

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=settings.KEYCLOAK_CLIENT_ID,
            issuer=f"{settings.KEYCLOAK_SERVER_URL}/realms/{settings.KEYCLOAK_REALM}",
        )
        return payload
    except JWTError as e:
        logger.warning("jwt_decode_failed", error=str(e))
        raise UnauthorizedError("Invalid or expired token")


def create_internal_token(user_id: str, email: str, permissions: list[str]) -> str:
    """Create an internal JWT for dev/local use (bypasses Keycloak)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "permissions": permissions,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_internal_token(token: str) -> dict:
    """Decode an internal JWT (dev/local mode)."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError as e:
        logger.warning("internal_jwt_decode_failed", error=str(e))
        raise UnauthorizedError("Invalid or expired token")