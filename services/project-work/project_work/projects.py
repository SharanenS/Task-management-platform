"""Owned project creation and reading; no implicit unrelated-project authority."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select

from .calendar import (
    TZDB_VERSION,
    CalendarError,
    day,
    local_boundary,
    normalize,
    working_hours,
)
from .models import CalendarVersion, Project, ProjectMember, ProjectPreview
from .transactions import lock_company


class ProjectError(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status


@dataclass(frozen=True)
class ProjectActor:
    issuer: str
    account_id: str
    role: str
    display_name: str


def identifier(value):
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ProjectError("invalid_identifier", 400) from None


def text_value(value, limit):
    if not isinstance(value, str) or any(ord(c) < 32 and c not in "\n\r\t" for c in value):
        raise ProjectError("invalid_project_details", 400)
    value = value.strip()
    if not 1 <= len(value) <= limit:
        raise ProjectError("invalid_project_details", 400)
    return value


def authorize(authority):
    actor = authority()
    if actor.role not in {"ADMIN", "MANAGER"}:
        raise ProjectError("project_access_denied", 403)
    return actor


def latest_calendar(s, issuer):
    return s.scalar(
        select(CalendarVersion)
        .where(CalendarVersion.issuer == issuer)
        .order_by(CalendarVersion.number.desc())
        .limit(1)
    )


def utc(value):
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone(UTC).isoformat()


def project_view(row):
    return {
        "id": row.id,
        "name": row.name,
        "objectives": row.objectives,
        "creator_id": row.creator_id,
        "creator_name": row.creator_name,
        "owner_id": row.owner_id,
        "owner_name": row.owner_name,
        "calendar_version_id": row.calendar_version_id,
        "calendar_number": row.calendar_number,
        "timezone": row.timezone,
        "tzdb_version": row.tzdb_version,
        "deadline_date": row.deadline_date,
        "approved_deadline": utc(row.approved_deadline),
        "deadline_local": row.deadline_local,
        "created_at": utc(row.created_at),
        "version": row.version,
    }


class ProjectService:
    def __init__(self, sessions, now=None):
        self.sessions = sessions
        self.now = now or (lambda: datetime.now(UTC))

    def _reader(self, authority):
        actor = authority()
        if actor.role in {"ADMIN", "MANAGER"}:
            return actor
        if actor.role == "EMPLOYEE":
            with self.sessions() as s:
                if s.scalar(
                    select(ProjectMember.id)
                    .where(
                        ProjectMember.issuer == actor.issuer,
                        ProjectMember.account_id == actor.account_id,
                        ProjectMember.active.is_(True),
                    )
                    .limit(1)
                ):
                    return actor
        raise ProjectError("project_access_denied", 403)

    def _visible(self, actor):
        return (Project.issuer == actor.issuer) & (
            True
            if actor.role == "ADMIN"
            else (
                Project.owner_id == actor.account_id
                if actor.role == "MANAGER"
                else Project.id.in_(
                    select(ProjectMember.project_id).where(
                        ProjectMember.issuer == actor.issuer,
                        ProjectMember.account_id == actor.account_id,
                        ProjectMember.active.is_(True),
                    )
                )
            )
        )

    def workspace(self, authority, page=0, search=""):
        actor = self._reader(authority)
        if (
            type(page) is not int
            or not 0 <= page <= 10000
            or not isinstance(search, str)
            or len(search) > 100
        ):
            raise ProjectError("invalid_page", 400)
        with self.sessions() as s:
            rows = s.scalars(
                select(Project)
                .where(
                    self._visible(actor),
                    func.lower(Project.name).contains(search.lower(), autoescape=True),
                )
                .order_by(Project.created_at.desc(), Project.id)
                .offset(page * 25)
                .limit(26)
            ).all()
            calendar = latest_calendar(s, actor.issuer)
            return {
                "projects": [project_view(r) for r in rows[:25]],
                "has_more": len(rows) > 25,
                "calendar": {
                    "id": calendar.id,
                    "number": calendar.number,
                    "timezone": json.loads(calendar.config)["timezone"],
                    "tzdb_version": calendar.tzdb_version,
                }
                if calendar and actor.role in {"ADMIN", "MANAGER"}
                else None,
            }

    def detail(self, authority, project_id):
        actor = self._reader(authority)
        with self.sessions() as s:
            row = s.scalar(
                select(Project).where(Project.id == identifier(project_id), self._visible(actor))
            )
            if not row:
                raise ProjectError("project_not_found", 404)
            return project_view(row)

    def preview(self, authority, value):
        actor = authorize(authority)
        name = text_value(value.get("name"), 150)
        objectives = text_value(value.get("objectives"), 5000)
        if "\n" in name or "\r" in name or "\t" in name:
            raise ProjectError("invalid_project_details", 400)
        with self.sessions() as s, s.begin():
            lock_company(s, actor.issuer)
            if authorize(authority) != actor:
                raise ProjectError("authority_changed", 403)
            calendar = latest_calendar(s, actor.issuer)
            if not calendar:
                raise ProjectError("company_calendar_required")
            if calendar.tzdb_version != TZDB_VERSION:
                raise ProjectError("unsupported_timezone_version")
            try:
                deadline = day(value.get("deadline_date"))
                config = normalize(json.loads(calendar.config))
                hours = working_hours(config, deadline)
                if not hours:
                    raise ProjectError("non_working_deadline")
                opening = local_boundary(deadline, hours["opens"], config["timezone"])
                closing = local_boundary(deadline, hours["closes"], config["timezone"])
                if opening >= closing:
                    raise ProjectError("invalid_project_deadline")
            except CalendarError as error:
                raise ProjectError(error.code, error.status) from None
            from .calendar import timezone_rules

            local = closing.astimezone(timezone_rules(config["timezone"])).isoformat()
            row = ProjectPreview(
                issuer=actor.issuer,
                actor_id=actor.account_id,
                actor_name=actor.display_name,
                name=name,
                objectives=objectives,
                deadline_date=deadline.isoformat(),
                approved_deadline=closing,
                deadline_local=local,
                calendar_version_id=calendar.id,
                calendar_number=calendar.number,
                timezone=config["timezone"],
                tzdb_version=calendar.tzdb_version,
                expires_at=self.now() + timedelta(minutes=10),
            )
            s.add(row)
            s.flush()
            return {
                "preview_id": row.id,
                "name": name,
                "objectives": objectives,
                "deadline_date": row.deadline_date,
                "approved_deadline": closing.isoformat(),
                "deadline_local": local,
                "calendar_number": calendar.number,
                "timezone": row.timezone,
                "tzdb_version": row.tzdb_version,
                "expires_at": row.expires_at.isoformat(),
                "past_deadline": closing < self.now(),
            }

    def create(self, authority, value):
        actor = authorize(authority)
        request_id, preview_id = (
            identifier(value.get("request_id")),
            identifier(value.get("preview_id")),
        )
        if value.get("confirm") is not True:
            raise ProjectError("confirmation_required", 400)
        with self.sessions() as s, s.begin():
            lock_company(s, actor.issuer)
            if authorize(authority) != actor:
                raise ProjectError("authority_changed", 403)
            previous = s.scalar(select(Project).where(Project.request_id == request_id))
            if previous:
                if (
                    previous.issuer != actor.issuer
                    or previous.creator_id != actor.account_id
                    or previous.preview_id != preview_id
                ):
                    raise ProjectError("request_conflict")
                if not (actor.role == "ADMIN" or previous.owner_id == actor.account_id):
                    raise ProjectError("project_not_found", 404)
                return project_view(previous)
            preview = s.get(ProjectPreview, preview_id)
            if (
                not preview
                or preview.issuer != actor.issuer
                or preview.actor_id != actor.account_id
            ):
                raise ProjectError("preview_not_owned", 404)
            expiry = (
                preview.expires_at
                if preview.expires_at.tzinfo
                else preview.expires_at.replace(tzinfo=UTC)
            )
            if expiry <= self.now():
                raise ProjectError("preview_expired")
            calendar = latest_calendar(s, actor.issuer)
            if not calendar or calendar.id != preview.calendar_version_id:
                raise ProjectError("stale_project_calendar")
            if preview.tzdb_version != TZDB_VERSION:
                raise ProjectError("unsupported_timezone_version")
            if s.scalar(select(Project.id).where(Project.preview_id == preview_id)):
                raise ProjectError("preview_already_used")
            row = Project(
                issuer=actor.issuer,
                request_id=request_id,
                preview_id=preview_id,
                name=preview.name,
                objectives=preview.objectives,
                creator_id=actor.account_id,
                creator_name=actor.display_name,
                owner_id=actor.account_id,
                owner_name=actor.display_name,
                deadline_date=preview.deadline_date,
                approved_deadline=preview.approved_deadline,
                deadline_local=preview.deadline_local,
                calendar_version_id=preview.calendar_version_id,
                calendar_number=preview.calendar_number,
                timezone=preview.timezone,
                tzdb_version=preview.tzdb_version,
                version=1,
            )
            s.add(row)
            s.flush()
            return project_view(row)
