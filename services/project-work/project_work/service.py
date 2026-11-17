"""Versioned calendar commands with current authority, previews and publication races."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, text

from .calendar import TZDB_VERSION, CalendarError, calculate, normalize
from .models import CalendarPreview, CalendarVersion


def identifier(value):
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise CalendarError("invalid_identifier", 400) from None


def serialize(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def describe(row):
    return {
        "id": row.id,
        "number": row.number,
        "tzdb_version": row.tzdb_version,
        "actor_id": row.actor_id,
        "created_at": row.created_at.isoformat(),
        "config": json.loads(row.config),
    }


class CalendarService:
    def __init__(self, sessions, now=None):
        self.sessions = sessions
        self.now = now or (lambda: datetime.now(UTC))

    def _current(self, s, issuer):
        return s.scalar(
            select(CalendarVersion)
            .where(CalendarVersion.issuer == issuer)
            .order_by(CalendarVersion.number.desc())
            .limit(1)
        )

    def _lock(self, s, issuer):
        if s.get_bind().dialect.name == "postgresql":
            key = int.from_bytes(
                hashlib.sha256(("calendar:" + issuer).encode()).digest()[:8], signed=True
            )
            s.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})

    def workspace(self, authority):
        with self.sessions() as s:
            issuer, actor = authority()
            rows = s.scalars(
                select(CalendarVersion)
                .where(CalendarVersion.issuer == issuer)
                .order_by(CalendarVersion.number.desc())
                .limit(50)
            ).all()
            return {
                "current": describe(rows[0]) if rows else None,
                "history": [
                    {
                        "id": r.id,
                        "number": r.number,
                        "tzdb_version": r.tzdb_version,
                        "actor_id": r.actor_id,
                        "created_at": r.created_at.isoformat(),
                    }
                    for r in rows
                ],
            }

    def preview(self, authority, value):
        config = normalize(value)
        encoded = serialize(config)
        with self.sessions() as s, s.begin():
            issuer, actor = authority()
            self._lock(s, issuer)
            # Re-resolve authority after waiting for a competing publication.
            if authority() != (issuer, actor):
                raise CalendarError("authority_changed", 403)
            current = self._current(s, issuer)
            row = CalendarPreview(
                issuer=issuer,
                actor_id=actor,
                base_version_id=current.id if current else None,
                config=encoded,
                config_hash=hashlib.sha256((TZDB_VERSION + ":" + encoded).encode()).hexdigest(),
                expires_at=self.now() + timedelta(minutes=10),
            )
            s.add(row)
            s.flush()
            previous = json.loads(current.config) if current else None
            changed = [k for k in config if previous is None or config[k] != previous[k]]
            if not changed:
                raise CalendarError("no_calendar_changes")
            return {
                "preview_id": row.id,
                "tzdb_version": TZDB_VERSION,
                "base_number": current.number if current else 0,
                "expires_at": row.expires_at.isoformat(),
                "config": config,
                "changed_sections": changed,
            }

    def publish(self, authority, value):
        request_id, preview_id = (
            identifier(value.get("request_id")),
            identifier(value.get("preview_id")),
        )
        if value.get("confirm") is not True:
            raise CalendarError("confirmation_required", 400)
        with self.sessions() as s, s.begin():
            issuer, actor = authority()
            self._lock(s, issuer)
            if authority() != (issuer, actor):
                raise CalendarError("authority_changed", 403)
            previous = s.scalar(
                select(CalendarVersion).where(CalendarVersion.request_id == request_id)
            )
            if previous:
                if (
                    previous.issuer != issuer
                    or previous.actor_id != actor
                    or previous.preview_id != preview_id
                ):
                    raise CalendarError("request_conflict")
                return describe(previous)
            preview = s.get(CalendarPreview, preview_id)
            if not preview or preview.issuer != issuer or preview.actor_id != actor:
                raise CalendarError("preview_not_owned", 404)
            expiry = (
                preview.expires_at.replace(tzinfo=UTC)
                if preview.expires_at.tzinfo is None
                else preview.expires_at
            )
            if expiry <= self.now():
                raise CalendarError("preview_expired")
            current = self._current(s, issuer)
            if preview.base_version_id != (current.id if current else None):
                raise CalendarError("stale_calendar_preview")
            if s.scalar(select(CalendarVersion.id).where(CalendarVersion.preview_id == preview_id)):
                raise CalendarError("preview_already_published")
            if preview.tzdb_version != TZDB_VERSION:
                raise CalendarError("unsupported_timezone_version")
            config = serialize(normalize(json.loads(preview.config)))
            if (
                hashlib.sha256((TZDB_VERSION + ":" + config).encode()).hexdigest()
                != preview.config_hash
            ):
                raise CalendarError("invalid_calendar_preview")
            row = CalendarVersion(
                issuer=issuer,
                number=(current.number + 1 if current else 1),
                preview_id=preview_id,
                request_id=request_id,
                actor_id=actor,
                config=config,
                config_hash=preview.config_hash,
            )
            s.add(row)
            s.flush()
            return describe(row)

    def calculation(self, authority, value):
        version_id = identifier(value.get("version_id"))
        with self.sessions() as s:
            issuer, actor = authority()
            row = s.get(CalendarVersion, version_id)
            if not row or row.issuer != issuer:
                raise CalendarError("calendar_version_not_found", 404)
            if row.tzdb_version != TZDB_VERSION:
                raise CalendarError("unsupported_timezone_version")
            return {
                "version_id": row.id,
                "version_number": row.number,
                **calculate(json.loads(row.config), value.get("start"), value.get("duration")),
            }
