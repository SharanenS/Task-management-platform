"""Application-wide constants: permissions, enums, etc."""

from enum import StrEnum


# ── Permissions ──────────────────────────────────────────────────
class Permission(StrEnum):
    USERS_CREATE = "users.create"
    USERS_READ = "users.read"
    USERS_UPDATE = "users.update"
    USERS_DELETE = "users.delete"

    PROJECTS_CREATE = "projects.create"
    PROJECTS_READ = "projects.read"
    PROJECTS_UPDATE = "projects.update"
    PROJECTS_DELETE = "projects.delete"

    REPORTS_CREATE = "reports.create"
    REPORTS_READ = "reports.read"
    REPORTS_GENERATE = "reports.generate"

    NOTIFICATIONS_READ = "notifications.read"

    AUDIT_READ = "audit.read"


# ── Enums ────────────────────────────────────────────────────────
class ProjectStatus(StrEnum):
    PLANNING = "PLANNING"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class ReportStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class NotificationType(StrEnum):
    REPORT_COMPLETED = "REPORT_COMPLETED"
    REPORT_FAILED = "REPORT_FAILED"
    USER_CREATED = "USER_CREATED"
    SYSTEM = "SYSTEM"


class AuditAction(StrEnum):
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    PERMISSION_CHANGED = "PERMISSION_CHANGED"
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    PROJECT_CREATED = "PROJECT_CREATED"
    PROJECT_UPDATED = "PROJECT_UPDATED"
    PROJECT_DELETED = "PROJECT_DELETED"
    REPORT_GENERATED = "REPORT_GENERATED"
    REPORT_FAILED = "REPORT_FAILED"