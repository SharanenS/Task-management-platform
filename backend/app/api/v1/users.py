"""User management endpoints (admin-provisioned)."""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db, require_permission
from app.core.constants import Permission
from app.schemas.user import UserResponse, UserCreate, UserListResponse, UserResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    request: Request,
    body: UserCreate,
    current_user: UserResponse = Depends(require_permission(Permission.USERS_CREATE)),
    db: AsyncSession = Depends(get_db),
):
    """Create a new employee account (requires users.create permission)."""
    service = UserService(db)
    return await service.create_user(
        body,
        created_by=current_user.id,
        ip_address=request.client.host if request.client else None,
    )


@router.get("", response_model=UserListResponse)
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: UserResponse = Depends(require_permission(Permission.USERS_READ)),
    db: AsyncSession = Depends(get_db),
):
    """List all employees (requires users.read permission)."""
    service = UserService(db)
    users, total = await service.list_users(skip, limit)
    return UserListResponse(users=users, total=total)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    current_user: UserResponse = Depends(require_permission(Permission.USERS_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Get an employee by ID (requires users.read permission)."""
    service = UserService(db)
    return await service.get_user(user_id)