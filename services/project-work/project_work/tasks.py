"""Project-specific planning with current authority, private detail and retained assignments."""

import json
from datetime import UTC, datetime

from sqlalchemy import select

from .coordination import fingerprint
from .delivery_inputs import advance_schedule
from .memberships import MembershipService, manages, read_actor
from .models import DeliveryState, ProjectMember, TaskAssignment, TaskChange, WorkTask
from .projects import ProjectError, identifier, project_view, utc
from .transactions import lock_company


def content(value, maximum):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ProjectError("invalid_task", 400)
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ProjectError("invalid_task", 400)
    return value.strip()


class TaskService:
    def __init__(self, sessions):
        self.sessions = sessions
        self.memberships = MembershipService(sessions)

    def scope(self, session, authority, project_id, planning=False):
        actor = read_actor(authority)
        project = self.memberships.project(session, actor, project_id)
        leader = (
            session.scalar(
                select(ProjectMember.id).where(
                    ProjectMember.project_id == project.id,
                    ProjectMember.issuer == actor.issuer,
                    ProjectMember.account_id == actor.account_id,
                    ProjectMember.active.is_(True),
                    ProjectMember.responsibility == "LEADER",
                )
            )
            is not None
            and actor.role == "EMPLOYEE"
        )
        if planning and not leader:
            raise ProjectError("task_planning_denied", 403)
        return actor, project, leader, leader or manages(actor, project)

    def member(self, session, project, account_id, directory):
        row = session.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id,
                ProjectMember.issuer == project.issuer,
                ProjectMember.account_id == identifier(account_id),
                ProjectMember.active.is_(True),
            )
        )
        if not row:
            raise ProjectError("task_assignee_ineligible")
        values = directory([row.account_id])
        candidate = next((r for r in values if r.get("account_id") == row.account_id), None)
        if (
            not candidate
            or candidate.get("active") is not True
            or candidate.get("role") != "EMPLOYEE"
        ):
            raise ProjectError("task_assignee_ineligible")
        return candidate

    def assignment(self, session, task):
        return session.scalar(
            select(TaskAssignment).where(
                TaskAssignment.task_id == task.id, TaskAssignment.ended_at.is_(None)
            )
        )

    def view(self, session, task, actor, supervisor):
        assignment = self.assignment(session, task)
        private = supervisor or (assignment and assignment.account_id == actor.account_id)
        details = None
        if private:
            history = (
                session.scalars(
                    select(TaskChange)
                    .where(
                        TaskChange.task_id == task.id,
                        TaskChange.action.in_(["CREATE", "EDIT", "ASSIGN"]),
                    )
                    .order_by(TaskChange.task_version.desc())
                    .limit(50)
                ).all()
                if supervisor
                else []
            )
            details = {
                "instructions": task.instructions,
                "acceptance_criteria": task.acceptance_criteria,
                "version": task.version,
                "assignee_id": assignment.account_id if assignment else None,
                "assigned_at": utc(assignment.started_at) if assignment else None,
                "history": [
                    {
                        "id": r.id,
                        "action": r.action,
                        "reason": r.reason,
                        "actor_name": r.actor_name,
                        "before": r.before,
                        "after": r.after,
                        "version": r.task_version,
                        "created_at": utc(r.created_at),
                    }
                    for r in history
                ],
            }
        return {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "assignee_name": assignment.display_name if assignment else None,
            "details": details,
        }

    def workspace(self, authority, project_id, page=0):
        if type(page) is not int or not 0 <= page <= 10000:
            raise ProjectError("invalid_page", 400)
        with self.sessions() as session:
            actor, project, leader, supervisor = self.scope(session, authority, project_id)
            rows = session.scalars(
                select(WorkTask)
                .where(WorkTask.project_id == project.id)
                .order_by(WorkTask.created_at, WorkTask.id)
                .offset(page * 25)
                .limit(26)
            ).all()
            return {
                "project": project_view(project),
                "can_plan": leader,
                "has_more": len(rows) > 25,
                "tasks": [self.view(session, r, actor, supervisor) for r in rows[:25]],
            }

    def candidates(self, authority, project_id, directory, page=0):
        if type(page) is not int or not 0 <= page <= 10000:
            raise ProjectError("invalid_page", 400)
        with self.sessions() as session:
            _, project, _, _ = self.scope(session, authority, project_id, True)
            rows = session.scalars(
                select(ProjectMember)
                .where(
                    ProjectMember.project_id == project.id,
                    ProjectMember.active.is_(True),
                    ProjectMember.issuer == project.issuer,
                )
                .order_by(ProjectMember.id)
                .offset(page * 25)
                .limit(26)
            ).all()
            ids = [r.account_id for r in rows[:25]]
            values = directory(ids) if ids else []
            return {
                "has_more": len(rows) > 25,
                "candidates": [
                    {"account_id": r["account_id"], "display_name": r["display_name"]}
                    for r in values
                    if r.get("account_id") in ids
                    and r.get("active") is True
                    and r.get("role") == "EMPLOYEE"
                ],
            }

    def change(self, authority, directory, value):
        shared = {
            "project_id",
            "request_id",
            "project_version",
            "action",
            "task_id",
            "version",
            "title",
            "instructions",
            "acceptance_criteria",
            "assignee_id",
            "reason",
            "confirm",
        }
        if (
            set(value) != shared
            or value["confirm"] is not True
            or value["action"] not in {"CREATE", "EDIT", "ASSIGN"}
        ):
            raise ProjectError("invalid_task", 400)
        if type(value["version"]) is not int or type(value["project_version"]) is not int:
            raise ProjectError("invalid_task", 400)
        request_id = identifier(value["request_id"])
        reason = content(value["reason"], 2000)
        digest = fingerprint(value)
        with self.sessions() as session, session.begin():
            actor, project, _, _ = self.scope(session, authority, value["project_id"], True)
            lock_company(session, actor.issuer)
            session.expire_all()
            current, project, _, _ = self.scope(session, authority, value["project_id"], True)
            if current != actor:
                raise ProjectError("task_planning_denied", 403)
            prior = session.scalar(select(TaskChange).where(TaskChange.request_id == request_id))
            if prior:
                task = session.get(WorkTask, prior.task_id)
                if (
                    task.project_id != project.id
                    or prior.actor_id != actor.account_id
                    or prior.request_hash != digest
                ):
                    raise ProjectError("task_request_conflict")
                return {
                    "task_id": task.id,
                    "version": prior.task_version,
                    "project_version": prior.project_version,
                }
            if value["project_version"] != project.version:
                raise ProjectError("stale_task")
            action = value["action"]
            task = None
            before = {}
            if action == "CREATE":
                if value["task_id"] is not None or value["version"] != 0:
                    raise ProjectError("invalid_task", 400)
            else:
                task = session.scalar(
                    select(WorkTask).where(
                        WorkTask.id == identifier(value["task_id"]),
                        WorkTask.project_id == project.id,
                    )
                )
                if not task:
                    raise ProjectError("task_not_found", 404)
                if task.version != value["version"]:
                    raise ProjectError("stale_task")
                if task.status != "PENDING":
                    raise ProjectError("task_lifecycle_requires_review")
                before = self.snapshot(session, task)
            if action in {"CREATE", "EDIT"}:
                title = content(value["title"], 200)
                instructions = content(value["instructions"], 8000)
                criteria = content(value["acceptance_criteria"], 8000)
            elif any(
                value[k] is not None for k in ("title", "instructions", "acceptance_criteria")
            ):
                raise ProjectError("invalid_task", 400)
            candidate = (
                self.member(session, project, value["assignee_id"], directory)
                if action in {"CREATE", "ASSIGN"}
                else None
            )
            if action == "EDIT" and value["assignee_id"] is not None:
                raise ProjectError("invalid_task", 400)
            if (
                action == "ASSIGN"
                and self.assignment(session, task).account_id == candidate["account_id"]
            ):
                raise ProjectError("task_assignment_unchanged")
            state = session.get(DeliveryState, project.id)
            advance_schedule(session, project.id, state.schedule_version if state else 0)
            if action == "CREATE":
                task = WorkTask(
                    project_id=project.id,
                    title=title,
                    instructions=instructions,
                    acceptance_criteria=criteria,
                    creator_id=actor.account_id,
                )
                session.add(task)
                session.flush()
            else:
                task.version += 1
            if action == "EDIT":
                task.title, task.instructions, task.acceptance_criteria = (
                    title,
                    instructions,
                    criteria,
                )
            if candidate:
                old = self.assignment(session, task)
                if old:
                    old.ended_at = datetime.now(UTC)
                    session.flush()
                session.add(
                    TaskAssignment(
                        task_id=task.id,
                        account_id=candidate["account_id"],
                        display_name=candidate["display_name"],
                        actor_id=actor.account_id,
                    )
                )
                session.flush()
            project.version += 1
            session.add(
                TaskChange(
                    task_id=task.id,
                    request_id=request_id,
                    request_hash=digest,
                    actor_id=actor.account_id,
                    actor_name=actor.display_name,
                    action=action,
                    reason=reason,
                    before=json.dumps(before, sort_keys=True),
                    after=json.dumps(self.snapshot(session, task), sort_keys=True),
                    task_version=task.version,
                    project_version=project.version,
                )
            )
            session.flush()
            return {"task_id": task.id, "version": task.version, "project_version": project.version}

    def snapshot(self, session, task):
        row = self.assignment(session, task)
        return {
            "title": task.title,
            "instructions": task.instructions,
            "acceptance_criteria": task.acceptance_criteria,
            "assignee_id": row.account_id if row else None,
            "assignee_name": row.display_name if row else None,
        }
