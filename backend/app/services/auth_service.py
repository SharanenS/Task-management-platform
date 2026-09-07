"""Authentication service — login, token management."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.core.exceptions import UnauthorizedError
from app.core.logging import get_logger
from app.core.security import create_internal_token, hash_password, verify_password
from app.models.audit_log import AuditLog
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, LoginResponse

logger = get_logger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)

    async def login(self, request: LoginRequest, ip_address: str | None = None) -> LoginResponse:
        """Authenticate user with email and password, return JWT."""
        user = await self.user_repo.get_by_email(request.email)

        if not user or not verify_password(request.password, user.password_hash):
            # Audit failed login
            audit = AuditLog(
                action=AuditAction.LOGIN_FAILURE,
                resource_type="auth",
                metadata_={"email": request.email},
                ip_address=ip_address,
            )
            self.session.add(audit)
            await self.session.flush()
            logger.warning("login_failed", email=request.email)
            raise UnauthorizedError("Invalid email or password")

        if not user.is_active:
            raise UnauthorizedError("Account is deactivated")

        # Collect permissions from all roles
        permissions: list[str] = []
        for role in user.roles:
            for perm in role.permissions:
                if perm.codename not in permissions:
                    permissions.append(perm.codename)

        token = create_internal_token(
            user_id=str(user.id),
            email=user.email,
            permissions=permissions,
        )

        # Audit successful login
        audit = AuditLog(
            user_id=user.id,
            action=AuditAction.LOGIN_SUCCESS,
            resource_type="auth",
            ip_address=ip_address,
        )
        self.session.add(audit)
        await self.session.flush()

        logger.info("login_success", email=user.email, user_id=str(user.id))
        return LoginResponse(access_token=token)