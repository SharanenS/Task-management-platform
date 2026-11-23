"""Project-owner coordination records; recipient responses arrive in a later stage."""

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import func, select

from .coordination_contracts import content, instant
from .memberships import MembershipService, read_actor
from .models import CoordinationFollowUp, CoordinationRecipient, CoordinationRecord, ProjectMember
from .projects import ProjectError, identifier, utc
from .transactions import lock_company


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class CoordinationService:
    def __init__(self, sessions):
        self.sessions = sessions
        self.memberships = MembershipService(sessions)

    def project(self, session, authority, project_id):
        actor = read_actor(authority)
        if actor.role not in {"ADMIN", "MANAGER"}:
            raise ProjectError("coordination_management_denied", 403)
        return actor, self.memberships.project(session, actor, project_id, management=True)

    def workspace(self, authority, project_id, page=0):
        if type(page) is not int or page < 0 or page > 10000:
            raise ProjectError("invalid_coordination", 400)
        with self.sessions() as session:
            _, project = self.project(session, authority, project_id)
            rows = session.scalars(
                select(CoordinationRecord)
                .where(
                    CoordinationRecord.project_id == project.id,
                    CoordinationRecord.issuer == project.issuer,
                )
                .order_by(CoordinationRecord.created_at.desc(), CoordinationRecord.id)
                .offset(page * 25)
                .limit(26)
            ).all()
            return {
                "records": [self.view(session, row) for row in rows[:25]],
                "has_more": len(rows) > 25,
            }

    def view(self, session, row):
        recipients = session.scalars(
            select(CoordinationRecipient)
            .where(CoordinationRecipient.record_id == row.id)
            .order_by(CoordinationRecipient.account_id)
        ).all()
        follow_ups = session.scalars(
            select(CoordinationFollowUp)
            .where(CoordinationFollowUp.record_id == row.id)
            .order_by(CoordinationFollowUp.created_at.desc(), CoordinationFollowUp.id)
            .limit(50)
        ).all()
        return {
            "id": row.id,
            "project_id": row.project_id,
            "kind": row.kind,
            "topic": row.topic,
            "details": row.details,
            "due_at": utc(row.due_at),
            "location": row.location,
            "acknowledgement_required": row.acknowledgement_required,
            "version": row.version,
            "created_at": utc(row.created_at),
            "overdue": instant(utc(row.due_at)) < datetime.now(UTC),
            "recipients": [
                {
                    "account_id": r.account_id,
                    "display_name": r.display_name,
                    "acknowledgement": "PENDING"
                    if row.acknowledgement_required
                    else "NOT_REQUIRED",
                    "response_state": "PENDING",
                }
                for r in recipients
            ],
            "follow_ups": [
                {
                    "id": f.id,
                    "actor_id": f.actor_id,
                    "note": f.note,
                    "next_follow_up_at": utc(f.next_follow_up_at),
                    "created_at": utc(f.created_at),
                }
                for f in follow_ups
            ],
        }

    def create(self, authority, eligible, value):
        required = {
            "project_id",
            "request_id",
            "kind",
            "topic",
            "details",
            "due_at",
            "location",
            "acknowledgement_required",
            "recipients",
            "confirm",
        }
        if set(value) != required or value["confirm"] is not True:
            raise ProjectError("invalid_coordination", 400)
        project_id, request_id = identifier(value["project_id"]), identifier(value["request_id"])
        if (
            value["kind"] not in {"UPDATE", "MEETING", "CHECK_IN"}
            or type(value["acknowledgement_required"]) is not bool
        ):
            raise ProjectError("invalid_coordination", 400)
        topic, details = content(value["topic"], 150), content(value["details"])
        due = instant(value["due_at"])
        location = content(value["location"], 300) if value["kind"] != "UPDATE" else ""
        if value["kind"] == "UPDATE" and value["location"] != "":
            raise ProjectError("invalid_coordination", 400)
        targets = value["recipients"]
        if not isinstance(targets, list) or not 1 <= len(targets) <= 25:
            raise ProjectError("invalid_coordination", 400)
        targets = sorted(identifier(t) for t in targets)
        if len(set(targets)) != len(targets):
            raise ProjectError("invalid_coordination", 400)
        digest = fingerprint({**value, "recipients": targets})
        with self.sessions() as session, session.begin():
            actor, project = self.project(session, authority, project_id)
            lock_company(session, actor.issuer)
            session.expire_all()
            actor, project = self.project(session, authority, project_id)
            previous = session.scalar(
                select(CoordinationRecord).where(CoordinationRecord.request_id == request_id)
            )
            if previous:
                if (
                    previous.issuer != actor.issuer
                    or previous.actor_id != actor.account_id
                    or previous.project_id != project.id
                    or previous.request_hash != digest
                ):
                    raise ProjectError("coordination_request_conflict")
                return self.view(session, previous)
            if due <= datetime.now(UTC):
                raise ProjectError("invalid_coordination_time", 400)
            names = {}
            for target in targets:
                membership = session.scalar(
                    select(ProjectMember).where(
                        ProjectMember.project_id == project.id,
                        ProjectMember.issuer == actor.issuer,
                        ProjectMember.account_id == target,
                        ProjectMember.active.is_(True),
                    )
                )
                if not membership:
                    raise ProjectError("coordination_recipient_ineligible", 409)
                current = eligible(target)
                if (
                    current.get("account_id") != target
                    or current.get("active") is not True
                    or current.get("role") != "EMPLOYEE"
                ):
                    raise ProjectError("coordination_recipient_ineligible", 409)
                names[target] = content(current.get("display_name"), 150)
            # Recheck requester after external current-account lookups, before committing.
            self.project(session, authority, project_id)
            row = CoordinationRecord(
                issuer=actor.issuer,
                project_id=project.id,
                request_id=request_id,
                request_hash=digest,
                actor_id=actor.account_id,
                kind=value["kind"],
                topic=topic,
                details=details,
                due_at=due,
                location=location,
                acknowledgement_required=value["acknowledgement_required"],
                version=1,
            )
            session.add(row)
            session.flush()
            session.add_all(
                [
                    CoordinationRecipient(record_id=row.id, account_id=t, display_name=names[t])
                    for t in targets
                ]
            )
            session.flush()
            return self.view(session, row)

    def follow_up(self, authority, value):
        if (
            set(value)
            != {
                "project_id",
                "record_id",
                "request_id",
                "version",
                "note",
                "next_follow_up_at",
                "confirm",
            }
            or value["confirm"] is not True
        ):
            raise ProjectError("invalid_coordination", 400)
        if type(value["version"]) is not int or value["version"] < 1:
            raise ProjectError("invalid_coordination", 400)
        request_id, record_id = identifier(value["request_id"]), identifier(value["record_id"])
        note, next_time = content(value["note"]), instant(value["next_follow_up_at"])
        digest = fingerprint(value)
        with self.sessions() as session, session.begin():
            actor, project = self.project(session, authority, value["project_id"])
            lock_company(session, actor.issuer)
            session.expire_all()
            actor, project = self.project(session, authority, value["project_id"])
            row = session.scalar(
                select(CoordinationRecord).where(
                    CoordinationRecord.id == record_id,
                    CoordinationRecord.project_id == project.id,
                    CoordinationRecord.issuer == actor.issuer,
                )
            )
            if not row:
                raise ProjectError("coordination_not_found", 404)
            previous = session.scalar(
                select(CoordinationFollowUp).where(CoordinationFollowUp.request_id == request_id)
            )
            if previous:
                if (
                    previous.record_id != row.id
                    or previous.actor_id != actor.account_id
                    or previous.request_hash != digest
                ):
                    raise ProjectError("coordination_request_conflict")
                return self.view(session, row)
            if row.version != value["version"]:
                raise ProjectError("coordination_stale")
            if next_time <= datetime.now(UTC):
                raise ProjectError("invalid_coordination_time", 400)
            if (
                session.scalar(
                    select(func.count())
                    .select_from(CoordinationFollowUp)
                    .where(CoordinationFollowUp.record_id == row.id)
                )
                >= 50
            ):
                raise ProjectError("coordination_follow_up_limit")
            session.add(
                CoordinationFollowUp(
                    record_id=row.id,
                    request_id=request_id,
                    request_hash=digest,
                    actor_id=actor.account_id,
                    note=note,
                    next_follow_up_at=next_time,
                )
            )
            row.version += 1
            session.flush()
            return self.view(session, row)
