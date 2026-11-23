"""Explicit, scoped absence contracts; session/logout state is never an authority input."""

from datetime import UTC, datetime

from sqlalchemy import select

from .coordination import fingerprint
from .coordination_contracts import content, instant
from .models import Project, ProjectMember, ReviewFallback
from .owner_decisions import OwnerDecisionService, clock_value
from .projects import ProjectError, identifier, utc


class ReviewFallbackService:
    def __init__(self, sessions, grant_roles, now=None):
        # The application must supply an explicit policy; no implicit permission default.
        if frozenset(grant_roles) not in {
            frozenset(),
            frozenset({"ADMIN"}),
            frozenset({"ADMIN", "MANAGER"}),
        }:
            raise ValueError("Explicit fallback grant policy required")
        self.grant_roles = frozenset(grant_roles)
        self.sessions = sessions
        self.now = now or (lambda: datetime.now(UTC))
        self.owners = OwnerDecisionService(sessions, self.now)

    def leader(self, session, project_id):
        return session.scalar(
            select(ProjectMember).where(
                ProjectMember.issuer
                == select(Project.issuer).where(Project.id == project_id).scalar_subquery(),
                ProjectMember.project_id == project_id,
                ProjectMember.active.is_(True),
                ProjectMember.responsibility == "LEADER",
            )
        )

    def active(self, session, row):
        leader = self.leader(session, row.project_id)
        same_leader = row.leader_id == (leader.account_id if leader else None)
        return (
            not row.revoked_at
            and clock_value(row.starts_at) <= self.now() < clock_value(row.ends_at)
            and same_leader
        )

    def view(self, session, row):
        return {
            "id": row.id,
            "leader_id": row.leader_id,
            "leader_name": row.leader_name,
            "scope": row.scope,
            "reason": row.reason,
            "actor_name": row.actor_name,
            "actor_id": row.actor_id,
            "starts_at": utc(row.starts_at),
            "ends_at": utc(row.ends_at),
            "created_at": utc(row.created_at),
            "active": self.active(session, row),
            "revoked_at": utc(row.revoked_at) if row.revoked_at else None,
            "revocation_reason": row.revocation_reason,
            "revoked_by": row.revoked_by,
        }

    def workspace(self, authority, project_id, page=0):
        if type(page) is not int or not 0 <= page <= 10000:
            raise ProjectError("invalid_owner_request", 400)
        with self.sessions() as session:
            actor, project = self.owners.project(session, authority, project_id)
            leader = self.leader(session, project.id)
            rows = session.scalars(
                select(ReviewFallback)
                .where(ReviewFallback.project_id == project.id)
                .order_by(ReviewFallback.created_at.desc(), ReviewFallback.id)
                .offset(page * 25)
                .limit(26)
            ).all()
            return {
                "can_record": actor.role in self.grant_roles,
                "leader_id": leader.account_id if leader else None,
                "leader_name": leader.display_name if leader else None,
                "records": [self.view(session, row) for row in rows[:25]],
                "has_more": len(rows) > 25,
            }

    def create(self, authority, value):
        if (
            set(value)
            != {
                "project_id",
                "request_id",
                "project_version",
                "leader_id",
                "scope",
                "reason",
                "starts_at",
                "ends_at",
                "confirm",
            }
            or value["confirm"] is not True
        ):
            raise ProjectError("invalid_fallback_record", 400)
        if (
            value["scope"] not in {"REVIEWS", "EXTENSIONS", "BOTH"}
            or type(value["project_version"]) is not int
        ):
            raise ProjectError("invalid_fallback_record", 400)
        request_id = identifier(value["request_id"])
        leader_id = identifier(value["leader_id"]) if value["leader_id"] else None
        starts, ends = instant(value["starts_at"]), instant(value["ends_at"])
        reason = content(value["reason"])
        if ends <= starts or ends <= self.now():
            raise ProjectError("invalid_fallback_period", 400)
        digest = fingerprint(value)
        with self.sessions() as session, session.begin():
            actor, project = self.owners.locked_project(session, authority, value["project_id"])
            if actor.role not in self.grant_roles:
                raise ProjectError("fallback_recording_denied", 403)
            prior = session.scalar(
                select(ReviewFallback).where(ReviewFallback.request_id == request_id)
            )
            if prior:
                if (
                    prior.project_id != project.id
                    or prior.actor_id != actor.account_id
                    or prior.request_hash != digest
                ):
                    raise ProjectError("owner_request_conflict")
                return self.view(session, prior)
            leader = self.leader(session, project.id)
            if project.version != value["project_version"] or leader_id != (
                leader.account_id if leader else None
            ):
                raise ProjectError("stale_fallback_leader")
            row = ReviewFallback(
                project_id=project.id,
                request_id=request_id,
                request_hash=digest,
                actor_id=actor.account_id,
                actor_name=actor.display_name,
                leader_id=leader_id,
                leader_name=leader.display_name if leader else None,
                scope=value["scope"],
                reason=reason,
                starts_at=starts,
                ends_at=ends,
                created_at=self.now(),
            )
            session.add(row)
            session.flush()
            return self.view(session, row)

    def revoke(self, authority, value):
        if (
            set(value) != {"project_id", "record_id", "request_id", "reason", "confirm"}
            or value["confirm"] is not True
        ):
            raise ProjectError("invalid_fallback_record", 400)
        request_id, record_id = identifier(value["request_id"]), identifier(value["record_id"])
        reason, digest = content(value["reason"]), fingerprint(value)
        with self.sessions() as session, session.begin():
            actor, project = self.owners.locked_project(session, authority, value["project_id"])
            if actor.role not in self.grant_roles:
                raise ProjectError("fallback_recording_denied", 403)
            row = session.scalar(
                select(ReviewFallback).where(
                    ReviewFallback.id == record_id, ReviewFallback.project_id == project.id
                )
            )
            if not row:
                raise ProjectError("fallback_not_found", 404)
            if row.revocation_request_id == request_id:
                if row.revoked_by != actor.account_id or row.revocation_hash != digest:
                    raise ProjectError("owner_request_conflict")
                return self.view(session, row)
            if row.revoked_at:
                raise ProjectError("fallback_already_revoked")
            duplicate = session.scalar(
                select(ReviewFallback.id).where(ReviewFallback.revocation_request_id == request_id)
            )
            if duplicate:
                raise ProjectError("owner_request_conflict")
            row.revoked_at, row.revoked_by, row.revocation_reason = (
                self.now(),
                actor.account_id,
                reason,
            )
            row.revocation_request_id, row.revocation_hash = request_id, digest
            session.flush()
            return self.view(session, row)

    def require_in_transaction(self, session, authority, project_id, scope, assessment_id=None):
        if not session.in_transaction():
            raise ProjectError("delivery_transaction_required")
        if scope not in {"REVIEWS", "EXTENSIONS"}:
            raise ProjectError("invalid_fallback_scope", 400)
        actor, project = self.owners.locked_project(session, authority, project_id)
        rows = session.scalars(
            select(ReviewFallback).where(
                ReviewFallback.project_id == project.id,
                ReviewFallback.revoked_at.is_(None),
                ReviewFallback.scope.in_([scope, "BOTH"]),
            )
        ).all()
        matching = next((row for row in rows if self.active(session, row)), None)
        if matching is None:
            raise ProjectError("explicit_fallback_required", 403)
        if scope == "EXTENSIONS":
            assessment, current = self.owners.assessment(session, project, assessment_id)
            if not current or assessment.status != "ASSESSED" or not assessment.forecast_at:
                raise ProjectError("owner_assessment_required")
            if clock_value(assessment.forecast_at) > self.owners.current_deadline(session, project):
                raise ProjectError("owner_deadline_decision_required")
        return {"record_id": matching.id, "actor_id": actor.account_id, "scope": scope}
