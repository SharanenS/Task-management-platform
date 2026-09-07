"""FastAPI dependencies: auth, permissions, database session."""

import uuid
from collections.abc import AsyncGenerator, Callable
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.logging import get_logger
from app.core.security import decode_internal_token
from app.db.session import get_async_session
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserResponse
from app.services.user_service import UserService

logger = get_logger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async for session in get_async_session():
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    request: Request,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Extract and validate the current user from the Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header")

    token = authorization.removeprefix("Bearer ")

    try:
        payload = decode_internal_token(token)
    except Exception:
        raise UnauthorizedError("Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token payload")

    user_service = UserService(db)
    try:
        user = await user_service.get_user(uuid.UUID(user_id))
    except Exception:
        raise UnauthorizedError("User not found")

    return user


CurrentUser = Annotated[UserResponse, Depends(get_current_user)]


def require_permission(permission: str) -> Callable:
    """Factory that returns a dependency checking the user has a specific permission."""

    async def _check_permission(current_user: CurrentUser) -> UserResponse:
        if permission not in current_user.permissions:
            logger.warning(
                "permission_denied",
                user_id=str(current_user.id),
                required=permission,
                user_permissions=current_user.permissions,
            )
            raise ForbiddenError(f"Missing required permission: {permission}")
        return current_user

    return _check_permission