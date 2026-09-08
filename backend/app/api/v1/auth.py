"""Authentication and authorization endpoints."""

from fastapi import APIRouter, Depends

from app.api.deps import (
    get_current_identity,
    require_admin,
    require_management,
    require_member,
)
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


@router.get("/admin")
async def admin_area(
    identity: AuthenticatedUser = Depends(require_admin),
):
    """ADMIN-only demonstration endpoint."""
    return {"message": "Admin area", "user": identity.sub, "roles": identity.roles}


@router.get("/management")
async def management_area(
    identity: AuthenticatedUser = Depends(require_management),
):
    """ADMIN or MANAGER demonstration endpoint."""
    return {"message": "Management area", "user": identity.sub, "roles": identity.roles}


@router.get("/member-area")
async def member_area(
    identity: AuthenticatedUser = Depends(require_member),
):
    """MEMBER-only demonstration endpoint."""
    return {"message": "Member area", "user": identity.sub, "roles": identity.roles}
