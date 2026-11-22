"""Project appointments, retained change history and current membership access."""

import hashlib
import json

from sqlalchemy import func, select

from .models import Project, ProjectMember, ProjectMembershipChange
from .projects import ProjectError, identifier, project_view, utc
from .transactions import lock_company

# S8 appointments are restricted to the owner-approved EMPLOYEE company role.
CONTRIBUTOR_ROLES = frozenset({"EMPLOYEE"})


def read_actor(authority):
    actor = authority()
    if actor.role not in {"ADMIN", "MANAGER", *CONTRIBUTOR_ROLES}:
        raise ProjectError("project_access_denied", 403)
    return actor


def manages(actor, project):
    return actor.role == "ADMIN" or (
        actor.role == "MANAGER" and actor.account_id == project.owner_id
    )


def member_state(row):
    return {
        "account_id": row.account_id,
        "display_name": row.display_name,
        "responsibility": row.responsibility,
        "duties": row.duties,
        "active": row.active,
    }


class MembershipService:
    def __init__(self, sessions):
        self.sessions = sessions

    def project(self, s, actor, project_id, management=False):
        row = s.scalar(
            select(Project).where(
                Project.id == identifier(project_id), Project.issuer == actor.issuer
            )
        )
        if not row:
            raise ProjectError("project_not_found", 404)
        if manages(actor, row):
            return row
        membership = s.scalar(
            select(ProjectMember.id).where(
                ProjectMember.project_id == row.id,
                ProjectMember.issuer == actor.issuer,
                ProjectMember.account_id == actor.account_id,
                ProjectMember.active.is_(True),
            )
        )
        if actor.role not in CONTRIBUTOR_ROLES or not membership:
            raise ProjectError("project_not_found", 404)
        if management:
            raise ProjectError("membership_management_denied", 403)
        return row

    def workspace(self, authority, project_id):
        actor = read_actor(authority)
        with self.sessions() as s:
            project = self.project(s, actor, project_id)
            management = manages(actor, project)
            query = select(ProjectMember).where(ProjectMember.project_id == project.id)
            if not management:
                query = query.where(ProjectMember.active.is_(True))
            rows = s.scalars(query.order_by(ProjectMember.created_at, ProjectMember.id)).all()
            own = next((r for r in rows if r.account_id == actor.account_id and r.active), None)
            history = (
                s.scalars(
                    select(ProjectMembershipChange)
                    .where(ProjectMembershipChange.project_id == project.id)
                    .order_by(ProjectMembershipChange.created_at.desc(), ProjectMembershipChange.id)
                    .limit(50)
                ).all()
                if management
                else []
            )
            return {
                "project": project_view(project),
                "can_manage": management,
                "responsibility": ("OWNER" if actor.account_id == project.owner_id else "ADMIN")
                if management
                else own.responsibility,
                "members": [
                    {
                        "id": r.id,
                        "display_name": r.display_name,
                        "account_id": r.account_id if management or r == own else None,
                        "responsibility": r.responsibility,
                        "active": r.active,
                        "duties": r.duties if management or r == own else None,
                    }
                    for r in rows
                ],
                "history": [
                    {
                        "id": r.id,
                        "actor_id": r.actor_id,
                        "target_id": r.target_id,
                        "action": r.action,
                        "before": r.before,
                        "after": r.after,
                        "project_version": r.project_version,
                        "created_at": utc(r.created_at),
                    }
                    for r in history
                ],
            }

    def candidates(self, authority, project_id, directory, page=0, search=""):
        actor = read_actor(authority)
        with self.sessions() as s:
            self.project(s, actor, project_id, True)
        if (
            type(page) is not int
            or not 0 <= page <= 10000
            or not isinstance(search, str)
            or len(search) > 100
        ):
            raise ProjectError("invalid_page", 400)
        return directory(page, search)

    def change(self, authority, eligible, value):
        actor = read_actor(authority)
        if set(value) != {
            "project_id",
            "request_id",
            "version",
            "account_id",
            "action",
            "responsibility",
            "duties",
            "confirm",
        }:
            raise ProjectError("invalid_membership_change", 400)
        project_id, request_id, account_id = (
            identifier(value[k]) for k in ("project_id", "request_id", "account_id")
        )
        action = value["action"]
        if action not in {"appoint", "remove"} or value["confirm"] is not True:
            raise ProjectError("confirmation_required", 400)
        if type(value["version"]) is not int or value["version"] < 1:
            raise ProjectError("invalid_membership_change", 400)
        if value["responsibility"] not in {"CONTRIBUTOR", "LEADER"}:
            raise ProjectError("invalid_membership_change", 400)
        duties = value["duties"]
        if (
            not isinstance(duties, str)
            or len(duties) > 1000
            or any(ord(c) < 32 and c not in "\r\n\t" for c in duties)
        ):
            raise ProjectError("invalid_membership_change", 400)
        fingerprint = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        with self.sessions() as s, s.begin():
            lock_company(s, actor.issuer)
            if read_actor(authority) != actor:
                raise ProjectError("authority_changed", 403)
            project = self.project(s, actor, project_id, True)
            previous = s.scalar(
                select(ProjectMembershipChange).where(
                    ProjectMembershipChange.request_id == request_id
                )
            )
            if previous:
                if (
                    previous.issuer != actor.issuer
                    or previous.project_id != project_id
                    or previous.actor_id != actor.account_id
                    or previous.request_hash != fingerprint
                ):
                    raise ProjectError("request_conflict")
                return {
                    "project_id": project_id,
                    "version": previous.project_version,
                    "change_id": previous.id,
                }
            if project.version != value["version"]:
                raise ProjectError("stale_project_membership")
            member = s.scalar(
                select(ProjectMember).where(
                    ProjectMember.project_id == project_id, ProjectMember.account_id == account_id
                )
            )
            before = member_state(member) if member else {}
            if action == "remove":
                if not member or not member.active:
                    raise ProjectError("membership_not_active")
                member.active = False
            else:
                target = eligible(account_id)
                if (
                    target.get("account_id") != account_id
                    or target.get("role") not in CONTRIBUTOR_ROLES
                    or target.get("active") is not True
                    or not isinstance(target.get("display_name"), str)
                    or not 1 <= len(target["display_name"]) <= 150
                ):
                    raise ProjectError("member_not_eligible")
                if account_id == project.owner_id:
                    raise ProjectError("member_not_eligible")
                if value["responsibility"] == "LEADER" and s.scalar(
                    select(ProjectMember.id).where(
                        ProjectMember.project_id == project_id,
                        ProjectMember.active.is_(True),
                        ProjectMember.responsibility == "LEADER",
                        ProjectMember.account_id != account_id,
                    )
                ):
                    raise ProjectError("leader_already_appointed")
                if member is None:
                    if (
                        s.scalar(
                            select(func.count())
                            .select_from(ProjectMember)
                            .where(ProjectMember.project_id == project_id)
                        )
                        >= 100
                    ):
                        raise ProjectError("project_membership_limit")
                    member = ProjectMember(
                        issuer=actor.issuer, project_id=project_id, account_id=account_id
                    )
                    s.add(member)
                member.display_name = target["display_name"]
                member.responsibility, member.duties, member.active = (
                    value["responsibility"],
                    duties.strip(),
                    True,
                )
                if before == member_state(member):
                    raise ProjectError("no_membership_change")
            project.version += 1
            history = ProjectMembershipChange(
                issuer=actor.issuer,
                project_id=project_id,
                request_id=request_id,
                request_hash=fingerprint,
                actor_id=actor.account_id,
                target_id=account_id,
                action=action,
                before=json.dumps(before, sort_keys=True),
                after=json.dumps(member_state(member), sort_keys=True),
                project_version=project.version,
            )
            s.add(history)
            s.flush()
            return {"project_id": project_id, "version": project.version, "change_id": history.id}
