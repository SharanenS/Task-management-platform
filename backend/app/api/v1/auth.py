"""Authentication endpoints."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate with email and password."""
    service = AuthService(db)
    return await service.login(body, ip_address=request.client.host if request.client else None)


@router.get("/me")
async def get_me(current_user: CurrentUser):
    """Get the current authenticated user."""
    return current_user


@router.post("/logout")
async def logout():
    """Logout — client should discard the token."""
    return {"message": "Logged out successfully"}