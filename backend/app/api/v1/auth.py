"""Authentication endpoints."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_identity
from app.core.security import AuthenticatedUser

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=AuthenticatedUser)
async def get_me(
    current_identity: AuthenticatedUser = Depends(get_current_identity),
):
    """
    Get the current authenticated identity.
    Validates the bearer token and returns the decoded claims.
    """
    return current_identity