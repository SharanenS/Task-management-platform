"""User service — business logic for employee provisioning."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.role import Role
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserResponse, UserUpdate

logger = get_logger(__name__)


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)

    async def create_user(
        self, data: UserCreate, created_by: uuid.UUID | None = None, ip_address: str | None = None
    ) -> UserResponse:
        """Create a new employee account (admin-provisioned)."""
        existing = await self.user_repo.get_by_email(data.email)
        if existing:
            raise ConflictError(f"User with email {data.email} already exists")

        user = User(
            name=data.name,
            email=data.email,
            password_hash=hash_password(data.password),
        )

        # Assign roles
        for role_name in data.role_names:
            stmt = select(Role).where(Role.name == role_name)
            result = await self.session.execute(stmt)
            role = result.scalar_one_or_none()
            if role:
                user.roles.append(role)

        user = await self.user_repo.create(user)

        # Audit log
        audit = AuditLog(
            user_id=created_by,
            action=AuditAction.USER_CREATED,
            resource_type="user",
            resource_id=str(user.id),
            metadata_={"email": user.email, "roles": data.role_names},
            ip_address=ip_address,
        )
        self.session.add(audit)

        logger.info("user_created", user_id=str(user.id), email=user.email)
        return self._to_response(user)

    async def get_user(self, user_id: uuid.UUID) -> UserResponse:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} not found")
        return self._to_response(user)

    async def list_users(self, skip: int = 0, limit: int = 100) -> tuple[list[UserResponse], int]:
        users, total = await self.user_repo.list_all(skip, limit)
        return [self._to_response(u) for u in users], total

    def _to_response(self, user: User) -> UserResponse:
        roles = [r.name for r in user.roles]
        permissions: list[str] = []
        for r in user.roles:
            for p in r.permissions:
                if p.codename not in permissions:
                    permissions.append(p.codename)
        return UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            is_active=user.is_active,
            roles=roles,
            permissions=permissions,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )