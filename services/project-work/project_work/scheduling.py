"""Actor-bound schedule previews and transactional, retained dependency revisions."""

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from .calendar import TZDB_VERSION, day
from .coordination import fingerprint
from .delivery_inputs import advance_schedule, record_assessment
from .models import (
    CalendarVersion,
    DeliveryState,
    ProjectMember,
    ScheduleChange,
    SchedulePreview,
    TaskDependency,
    TaskExecution,
    TaskSchedule,
    WorkTask,
)
from .owner_decisions import OwnerDecisionService
from .projects import ProjectError, identifier, project_view, utc
from .schedule_graph import MAX_TASKS, analyze
from .tasks import TaskService, content
from .transactions import lock_company


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class SchedulingService:
    def __init__(self, sessions, now=None):
        self.sessions = sessions
        self.tasks = TaskService(sessions)
        self.now = now or (lambda: datetime.now(UTC))

    def network(self, session, project, directory):
        tasks = session.scalars(
            select(WorkTask)
            .where(WorkTask.project_id == project.id)
            .order_by(WorkTask.created_at, WorkTask.id)
            .limit(MAX_TASKS + 1)
        ).all()
        if len(tasks) > MAX_TASKS:
            raise ProjectError("schedule_limit", 400)
        calendar = session.get(CalendarVersion, project.calendar_version_id)
        if (
            not calendar
            or calendar.issuer != project.issuer
            or calendar.tzdb_version != TZDB_VERSION
        ):
            raise ProjectError("schedule_calendar_unavailable")
        members = set(
            session.scalars(
                select(ProjectMember.account_id).where(
                    ProjectMember.project_id == project.id,
                    ProjectMember.active.is_(True),
                    ProjectMember.issuer == project.issuer,
                )
            ).all()
        )
        assignments = {t.id: self.tasks.assignment(session, t) for t in tasks}
        ids = sorted({a.account_id for a in assignments.values() if a})
        eligible = set()
        for offset in range(0, len(ids), 25):
            batch = ids[offset : offset + 25]
            eligible.update(
                r["account_id"]
                for r in directory(batch)
                if r.get("account_id") in batch
                and r.get("active") is True
                and r.get("role") == "EMPLOYEE"
            )
        executions = {
            r.task_id: r
            for r in session.scalars(
                select(TaskExecution).where(TaskExecution.task_id.in_([t.id for t in tasks]))
            )
        }
        nodes = []
        for task in tasks:
            plan = session.get(TaskSchedule, task.id)
            assignment = assignments[task.id]
            execution = executions.get(task.id)
            if plan and plan.calendar_version_id != calendar.id:
                raise ProjectError("schedule_calendar_unavailable")
            nodes.append(
                {
                    "id": task.id,
                    "title": task.title,
                    "version": task.version,
                    "status": task.status,
                    "actual_completed_at": utc(execution.completed_at)
                    if execution and execution.completed_at
                    else None,
                    "assignee_id": assignment.account_id if assignment else None,
                    "assignee_name": assignment.display_name if assignment else None,
                    "eligible": bool(assignment and assignment.account_id in members & eligible),
                    "requested_start": plan.requested_start if plan else None,
                    "duration": plan.duration if plan else None,
                    "prerequisites": sorted(
                        session.scalars(
                            select(TaskDependency.prerequisite_id).where(
                                TaskDependency.task_id == task.id
                            )
                        ).all()
                    ),
                }
            )
        return nodes, json.loads(calendar.config)

    def source_hash(self, session, project, nodes, config):
        state = session.get(DeliveryState, project.id)
        return fingerprint(
            {
                "nodes": nodes,
                "calendar": config,
                "calendar_id": project.calendar_version_id,
                "timezone": project.timezone,
                "tzdb_version": project.tzdb_version,
                "schedule_version": state.schedule_version if state else 0,
                "deadline": OwnerDecisionService(self.sessions)
                .current_deadline(session, project)
                .isoformat(),
            }
        )

    def calculate(self, config, nodes):
        return analyze(config, nodes, self.now())

    def locked_scope(self, session, authority, project_id):
        actor, project, _, _ = self.tasks.scope(session, authority, project_id, True)
        lock_company(session, actor.issuer)
        session.expire_all()
        current, project, _, _ = self.tasks.scope(session, authority, project_id, True)
        if current != actor:
            raise ProjectError("task_planning_denied", 403)
        return actor, project

    def preview(self, authority, directory, value):
        if set(value) != {
            "project_id",
            "task_id",
            "project_version",
            "version",
            "requested_start",
            "duration",
            "prerequisites",
            "reason",
        }:
            raise ProjectError("invalid_schedule", 400)
        day(value["requested_start"])
        reason = content(value["reason"], 2000)
        if (
            type(value["duration"]) is not int
            or not 1 <= value["duration"] <= 3660
            or not isinstance(value["prerequisites"], list)
            or len(value["prerequisites"]) > MAX_TASKS
            or type(value["project_version"]) is not int
            or type(value["version"]) is not int
        ):
            raise ProjectError("invalid_schedule", 400)
        dependencies = [identifier(i) for i in value["prerequisites"]]
        with self.sessions() as session, session.begin():
            actor, project = self.locked_scope(session, authority, value["project_id"])
            nodes, config = self.network(session, project, directory)
            source_hash = self.source_hash(session, project, nodes, config)
            task_id = identifier(value["task_id"])
            target = next((r for r in nodes if r["id"] == task_id), None)
            if not target:
                raise ProjectError("task_not_found", 404)
            if project.version != value["project_version"] or target["version"] != value["version"]:
                raise ProjectError("stale_schedule")
            if target["status"] != "PENDING" or not target["eligible"]:
                raise ProjectError("schedule_task_not_plannable")
            before = self.calculate(config, nodes)
            target.update(
                requested_start=value["requested_start"],
                duration=value["duration"],
                prerequisites=dependencies,
            )
            after = self.calculate(config, nodes)
            previous = {r["id"]: r for r in before["tasks"]}
            for row in after["tasks"]:
                node = next(n for n in nodes if n["id"] == row["id"])
                if node["status"] not in {"PENDING", "CANCELLED"} and any(
                    row[k] != previous[row["id"]][k] for k in ("starts_at", "due_at")
                ):
                    raise ProjectError("schedule_affects_started_task")
            now = self.now()
            preview = SchedulePreview(
                project_id=project.id,
                actor_id=actor.account_id,
                project_version=project.version,
                source_hash=source_hash,
                payload=encode(
                    {
                        **value,
                        "project_id": project.id,
                        "task_id": task_id,
                        "prerequisites": dependencies,
                        "reason": reason,
                    }
                ),
                result=encode(after),
                created_at=now,
                valid_until=now + timedelta(minutes=10),
            )
            session.add(preview)
            session.flush()
            return {
                "preview_id": preview.id,
                "valid_until": utc(preview.valid_until),
                "before": before,
                "after": after,
                "calendar_number": project.calendar_number,
                "timezone": project.timezone,
                "approved_deadline": OwnerDecisionService(self.sessions)
                .current_deadline(session, project)
                .isoformat(),
                "exceeds_deadline": bool(
                    after["forecast_at"]
                    and datetime.fromisoformat(after["forecast_at"])
                    > OwnerDecisionService(self.sessions).current_deadline(session, project)
                ),
            }

    def commit(self, authority, directory, value):
        if (
            set(value) != {"project_id", "preview_id", "request_id", "confirm"}
            or value["confirm"] is not True
        ):
            raise ProjectError("invalid_schedule", 400)
        request_id, preview_id = identifier(value["request_id"]), identifier(value["preview_id"])
        digest = fingerprint(value)
        with self.sessions() as session, session.begin():
            actor, project = self.locked_scope(session, authority, value["project_id"])
            prior = session.scalar(
                select(ScheduleChange).where(ScheduleChange.request_id == request_id)
            )
            if prior:
                if (
                    prior.project_id != project.id
                    or prior.actor_id != actor.account_id
                    or prior.request_hash != digest
                ):
                    raise ProjectError("schedule_request_conflict")
                return {
                    "project_version": prior.project_version,
                    "schedule_version": prior.schedule_version,
                }
            preview = session.get(SchedulePreview, preview_id)
            if (
                not preview
                or preview.project_id != project.id
                or preview.actor_id != actor.account_id
            ):
                raise ProjectError("schedule_preview_unavailable")
            if (
                datetime.fromisoformat(utc(preview.valid_until)) <= self.now()
                or preview.project_version != project.version
                or session.scalar(
                    select(ScheduleChange.id).where(ScheduleChange.preview_id == preview.id)
                )
            ):
                raise ProjectError("stale_schedule")
            nodes, config = self.network(session, project, directory)
            if self.source_hash(session, project, nodes, config) != preview.source_hash:
                raise ProjectError("stale_schedule")
            before = self.calculate(config, nodes)
            payload = json.loads(preview.payload)
            target = next(n for n in nodes if n["id"] == payload["task_id"])
            target.update(
                requested_start=payload["requested_start"],
                duration=payload["duration"],
                prerequisites=payload["prerequisites"],
            )
            after = self.calculate(config, nodes)
            # Passage of a cutoff or external eligibility changes requires a new impact preview.
            if after != json.loads(preview.result):
                raise ProjectError("stale_schedule")
            state = session.get(DeliveryState, project.id)
            schedule_version = advance_schedule(
                session, project.id, state.schedule_version if state else 0
            )
            for node, result in zip(nodes, after["tasks"], strict=True):
                if node["requested_start"] is None:
                    continue
                row = session.get(TaskSchedule, node["id"])
                snapshot = encode(result)
                changed = not row or row.current != snapshot
                if not row:
                    row = TaskSchedule(
                        task_id=node["id"],
                        requested_start=node["requested_start"],
                        duration=node["duration"],
                        calendar_version_id=project.calendar_version_id,
                        original=snapshot,
                        current=snapshot,
                    )
                    session.add(row)
                else:
                    row.requested_start, row.duration, row.current = (
                        node["requested_start"],
                        node["duration"],
                        snapshot,
                    )
                if changed or node["id"] == payload["task_id"]:
                    session.get(WorkTask, node["id"]).version += 1
            session.execute(
                delete(TaskDependency).where(TaskDependency.task_id == payload["task_id"])
            )
            for prerequisite in payload["prerequisites"]:
                session.add(
                    TaskDependency(task_id=payload["task_id"], prerequisite_id=prerequisite)
                )
            project.version += 1
            session.add(
                ScheduleChange(
                    project_id=project.id,
                    preview_id=preview.id,
                    request_id=request_id,
                    request_hash=digest,
                    actor_id=actor.account_id,
                    actor_name=actor.display_name,
                    reason=payload["reason"],
                    before=encode(before),
                    after=encode(after),
                    schedule_version=schedule_version,
                    project_version=project.version,
                    created_at=self.now(),
                )
            )
            session.flush()
            assessment = record_assessment(
                session,
                project.id,
                schedule_version,
                project.version,
                after["state"],
                after["forecast_at"],
                "Dependency schedule; capacity is not guaranteed.",
                self.now(),
            )
            cutoffs = [
                datetime.fromisoformat(r["due_at"])
                for r in after["tasks"]
                if r["due_at"]
                and next(n for n in nodes if n["id"] == r["id"])["status"] != "COMPLETED"
                and datetime.fromisoformat(r["due_at"]) >= self.now()
            ]
            if cutoffs:
                assessment.valid_until = min(assessment.valid_until, *cutoffs)
            return {"project_version": project.version, "schedule_version": schedule_version}

    def require_ready_in_transaction(self, session, authority, project_id, task_id, directory):
        """Future start handlers must call this before writing, in the same transaction."""
        if not session.in_transaction() or session.new or session.dirty or session.deleted:
            raise ProjectError("schedule_transaction_required")
        actor, project, _, _ = self.tasks.scope(session, authority, project_id)
        lock_company(session, actor.issuer)
        session.expire_all()
        current, project, _, _ = self.tasks.scope(session, authority, project_id)
        if current != actor or actor.role != "EMPLOYEE":
            raise ProjectError("task_access_denied", 403)
        nodes, config = self.network(session, project, directory)
        task = next((n for n in nodes if n["id"] == identifier(task_id)), None)
        if not task or task["assignee_id"] != actor.account_id:
            raise ProjectError("task_access_denied", 403)
        result = next(r for r in self.calculate(config, nodes)["tasks"] if r["id"] == task["id"])
        if task["status"] != "PENDING" or result["readiness"] != "READY":
            raise ProjectError("task_prerequisites_not_ready")
        return result

    def workspace(self, authority, directory, project_id):
        with self.sessions() as session:
            actor, project, leader, supervisor = self.tasks.scope(session, authority, project_id)
            nodes, config = self.network(session, project, directory)
            result = self.calculate(config, nodes)
            visible = {n["id"] for n in nodes if supervisor or n["assignee_id"] == actor.account_id}
            labels = {n["id"]: n for n in nodes}
            rows = []
            for row in result["tasks"]:
                if row["id"] not in visible:
                    continue
                plan = session.get(TaskSchedule, row["id"])
                rows.append(
                    {
                        **row,
                        "title": labels[row["id"]]["title"],
                        "version": labels[row["id"]]["version"],
                        "status": labels[row["id"]]["status"],
                        "assignee_name": labels[row["id"]]["assignee_name"],
                        "original": json.loads(plan.original) if plan else None,
                    }
                )
            history = (
                session.scalars(
                    select(ScheduleChange)
                    .where(ScheduleChange.project_id == project.id)
                    .order_by(ScheduleChange.created_at.desc())
                    .limit(25)
                ).all()
                if supervisor
                else []
            )
            return {
                "project": project_view(project),
                "can_plan": leader,
                "state": result["state"] if supervisor else None,
                "forecast_at": result["forecast_at"] if supervisor else None,
                "timezone": project.timezone,
                "calendar_number": project.calendar_number,
                "current_deadline": OwnerDecisionService(self.sessions)
                .current_deadline(session, project)
                .isoformat(),
                "tasks": rows,
                "overlaps": result["overlaps"] if supervisor else [],
                "history": [
                    {
                        "id": r.id,
                        "actor_name": r.actor_name,
                        "reason": r.reason,
                        "created_at": utc(r.created_at),
                        "before": r.before,
                        "after": r.after,
                    }
                    for r in history
                ],
            }
