import base64
import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.keycloak_admin import (
    KeycloakAdmin,
    KeycloakCollisionError,
    KeycloakUnavailableError,
    keycloak_admin,
)
from app.models import (
    ApplicationRole,
    Employee,
    ProvisioningRequest,
    ProvisioningStatus,
)


class AdminError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class EmployeePage:
    items: list[Employee]
    next_cursor: str | None
    has_next_page: bool


def require_admin(session: Session, actor_subject: str) -> Employee:
    actor = session.scalar(
        select(Employee).where(
            Employee.keycloak_subject == actor_subject,
            Employee.active.is_(True),
            Employee.provisioning_status == ProvisioningStatus.COMPLETE,
        )
    )
    if actor is None or actor.role != ApplicationRole.ADMIN:
        raise AdminError("FORBIDDEN", "Administrator access is required.", 403)
    return actor


def _cursor_value(cursor: str | None) -> uuid.UUID | None:
    if not cursor:
        return None
    try:
        return uuid.UUID(base64.urlsafe_b64decode(cursor + "===").decode())
    except (ValueError, UnicodeDecodeError):
        raise AdminError("INVALID_INPUT", "The pagination cursor is invalid.") from None


def _encode_cursor(employee_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(str(employee_id).encode()).decode().rstrip("=")


def list_employees(
    session: Session,
    actor_subject: str,
    *,
    first: int,
    after: str | None,
    search: str | None,
    role: ApplicationRole | None,
    active: bool | None,
) -> EmployeePage:
    require_admin(session, actor_subject)
    if first < 1 or first > 50:
        raise AdminError("INVALID_INPUT", "Page size must be between 1 and 50.")
    query = select(Employee)
    cursor_id = _cursor_value(after)
    if cursor_id:
        query = query.where(Employee.id > cursor_id)
    if search and search.strip():
        pattern = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(Employee.display_name).like(pattern),
                func.lower(Employee.username).like(pattern),
                func.lower(Employee.email).like(pattern),
            )
        )
    if role:
        query = query.where(Employee.role == role)
    if active is not None:
        query = query.where(Employee.active.is_(active))
    items = list(session.scalars(query.order_by(Employee.id).limit(first + 1)))
    has_next = len(items) > first
    items = items[:first]
    return EmployeePage(
        items=items,
        next_cursor=_encode_cursor(items[-1].id) if has_next and items else None,
        has_next_page=has_next,
    )


def get_employee_detail(session: Session, actor_subject: str, employee_id: uuid.UUID) -> Employee:
    require_admin(session, actor_subject)
    employee = session.get(Employee, employee_id)
    if employee is None:
        raise AdminError("NOT_FOUND", "Employee was not found.", 404)
    return employee


def _fingerprint(values: Mapping[str, object]) -> str:
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def provision_employee(
    session: Session,
    actor_subject: str,
    *,
    idempotency_key: str,
    username: str,
    email: str,
    display_name: str,
    role: ApplicationRole,
    active: bool,
    temporary_password: str,
    keycloak: KeycloakAdmin = keycloak_admin,
) -> Employee:
    require_admin(session, actor_subject)
    username = username.strip().lower()
    email = email.strip().lower()
    display_name = display_name.strip()
    if not 3 <= len(username) <= 100 or not username.replace(".", "").replace("-", "").isalnum():
        raise AdminError("INVALID_INPUT", "Username format is invalid.")
    if "@" not in email or len(email) > 320:
        raise AdminError("INVALID_INPUT", "Email format is invalid.")
    if not 2 <= len(display_name) <= 200:
        raise AdminError("INVALID_INPUT", "Display name must contain 2 to 200 characters.")
    if len(temporary_password) < 12:
        raise AdminError("INVALID_INPUT", "Temporary password must contain at least 12 characters.")
    if not 8 <= len(idempotency_key) <= 100:
        raise AdminError("INVALID_INPUT", "Idempotency key is invalid.")
    values = {
        "username": username,
        "email": email,
        "display_name": display_name,
        "role": role.value,
        "active": active,
    }
    fingerprint = _fingerprint(values)
    previous = session.get(ProvisioningRequest, idempotency_key)
    if previous:
        if previous.request_fingerprint != fingerprint:
            raise AdminError("IDEMPOTENCY_CONFLICT", "The retry key was already used.", 409)
        if previous.employee_id:
            employee = session.get(Employee, previous.employee_id)
            if employee:
                return employee
    collision = session.scalar(
        select(Employee).where(or_(Employee.username == username, Employee.email == email))
    )
    if collision:
        raise AdminError("DUPLICATE_EMPLOYEE", "Username or email is already in use.", 409)
    request = previous or ProvisioningRequest(
        idempotency_key=idempotency_key, request_fingerprint=fingerprint
    )
    if previous is None:
        session.add(request)
        try:
            session.commit()
        except IntegrityError as error:
            session.rollback()
            raise AdminError(
                "IDEMPOTENCY_CONFLICT", "The retry key was already used.", 409
            ) from error
    try:
        existing = keycloak.find_owned_user(username, idempotency_key)
        subject = (
            existing.subject
            if existing
            else keycloak.create_disabled_user(
                username=username,
                email=email,
                display_name=display_name,
                temporary_password=temporary_password,
                ownership_key=idempotency_key,
            )
        )
    except KeycloakCollisionError as error:
        raise AdminError(
            "IDENTITY_COLLISION", "The identity cannot be provisioned.", 409
        ) from error
    except KeycloakUnavailableError as error:
        raise AdminError(
            "SERVICE_UNAVAILABLE", "Identity administration is unavailable.", 503
        ) from error
    employee = Employee(
        keycloak_subject=subject,
        username=username,
        email=email,
        display_name=display_name,
        role=role,
        active=False,
        provisioning_status=ProvisioningStatus.RECONCILIATION_REQUIRED,
    )
    session.add(employee)
    try:
        session.flush()
        request.employee_id = employee.id
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise AdminError(
            "DUPLICATE_EMPLOYEE", "Username or email is already in use.", 409
        ) from error
    try:
        keycloak.set_enabled(subject, active)
        employee.active = active
        employee.provisioning_status = ProvisioningStatus.COMPLETE
        employee.version += 1
        session.commit()
    except KeycloakUnavailableError:
        employee.active = False
        employee.provisioning_status = ProvisioningStatus.RECONCILIATION_REQUIRED
        session.commit()
    return employee


def update_role(
    session: Session,
    actor_subject: str,
    employee_id: uuid.UUID,
    role: ApplicationRole,
) -> Employee:
    actor = require_admin(session, actor_subject)
    employee = get_employee_detail(session, actor_subject, employee_id)
    if employee.id == actor.id and role != ApplicationRole.ADMIN:
        raise AdminError("SELF_PROTECTED", "You cannot remove your own administrator role.", 409)
    if employee.role == ApplicationRole.ADMIN and role != ApplicationRole.ADMIN and employee.active:
        active_admins = session.scalar(
            select(func.count())
            .select_from(Employee)
            .where(and_(Employee.role == ApplicationRole.ADMIN, Employee.active.is_(True)))
        )
        if active_admins == 1:
            raise AdminError("FINAL_ADMIN", "The final active administrator is protected.", 409)
    employee.role = role
    employee.version += 1
    session.commit()
    return employee


def set_employee_active(
    session: Session,
    actor_subject: str,
    employee_id: uuid.UUID,
    active: bool,
    *,
    keycloak: KeycloakAdmin = keycloak_admin,
) -> Employee:
    actor = require_admin(session, actor_subject)
    employee = get_employee_detail(session, actor_subject, employee_id)
    if employee.id == actor.id and not active:
        raise AdminError("SELF_PROTECTED", "You cannot deactivate your own account.", 409)
    if employee.role == ApplicationRole.ADMIN and employee.active and not active:
        active_admins = session.scalar(
            select(func.count())
            .select_from(Employee)
            .where(and_(Employee.role == ApplicationRole.ADMIN, Employee.active.is_(True)))
        )
        if active_admins == 1:
            raise AdminError("FINAL_ADMIN", "The final active administrator is protected.", 409)
    if employee.active == active and employee.provisioning_status == ProvisioningStatus.COMPLETE:
        return employee
    employee.active = False
    employee.provisioning_status = ProvisioningStatus.RECONCILIATION_REQUIRED
    employee.version += 1
    session.commit()
    try:
        keycloak.set_enabled(employee.keycloak_subject, active)
    except KeycloakUnavailableError as error:
        raise AdminError(
            "RECONCILIATION_REQUIRED",
            "The account is safe but identity synchronization must be retried.",
            503,
        ) from error
    employee.active = active
    employee.provisioning_status = ProvisioningStatus.COMPLETE
    employee.version += 1
    session.commit()
    return employee


def reconcile_employee(
    session: Session,
    actor_subject: str,
    employee_id: uuid.UUID,
    *,
    keycloak: KeycloakAdmin = keycloak_admin,
) -> Employee:
    require_admin(session, actor_subject)
    employee = get_employee_detail(session, actor_subject, employee_id)
    desired_active = employee.active
    if employee.provisioning_status == ProvisioningStatus.RECONCILIATION_REQUIRED:
        desired_active = False
    try:
        keycloak.set_enabled(employee.keycloak_subject, desired_active)
    except KeycloakUnavailableError as error:
        raise AdminError(
            "RECONCILIATION_REQUIRED", "Identity synchronization is still unavailable.", 503
        ) from error
    employee.active = desired_active
    employee.provisioning_status = ProvisioningStatus.COMPLETE
    employee.version += 1
    session.commit()
    return employee
