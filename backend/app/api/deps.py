"""FastAPI dependencies for authentication and authorization."""

from collections.abc import AsyncGenerator

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import AuthenticatedUser, Role, verify_jwt_token
from app.db.session import async_session_factory

logger = get_logger(__name__)
oauth2_scheme = HTTPBearer()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_identity(
    token: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
) -> AuthenticatedUser:
    """Validate Bearer token and return the authenticated identity."""
    try:
        identity = verify_jwt_token(token.credentials)
        return identity
    except jwt.ExpiredSignatureError:
        logger.info("token_expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.info("token_invalid", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error("token_validation_unexpected_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


class RoleChecker:
    """
    Reusable FastAPI dependency for role-based authorization.

    Usage in routers:
        require_admin = RoleChecker(Role.ADMIN)
        require_management = RoleChecker(Role.ADMIN, Role.MANAGER)

        @router.get("/admin", dependencies=[Depends(require_admin)])
        async def admin_endpoint(): ...
    """

    def __init__(self, *allowed_roles: Role) -> None:
        if not allowed_roles:
            raise ValueError("RoleChecker requires at least one allowed role.")
        self.allowed_roles = set(allowed_roles)

    async def __call__(
        self, identity: AuthenticatedUser = Depends(get_current_identity)
    ) -> AuthenticatedUser:
        """Check that the authenticated user has at least one of the allowed roles."""
        if not self.allowed_roles.intersection(identity.roles):
            logger.info(
                "authorization_denied",
                sub=identity.sub,
                required=sorted(self.allowed_roles),
                actual=sorted(identity.roles),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return identity


# Pre-built authorization dependencies for common patterns
require_admin = RoleChecker(Role.ADMIN)
require_manager = RoleChecker(Role.MANAGER)
require_member = RoleChecker(Role.MEMBER)
require_management = RoleChecker(Role.ADMIN, Role.MANAGER)
