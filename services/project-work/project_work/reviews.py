"""Current-assignee execution and version-bound reviews with explicit self/fallback audit."""

import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select

from .coordination import fingerprint
from .delivery_inputs import advance_schedule
from .memberships import manages
from .models import (
    DeliveryState,
    ProjectMember,
    ReviewFallback,
    TaskChange,
    TaskExecution,
    TaskReviewDecision,
    TaskSchedule,
    TaskSubmission,
    WorkTask,
)
from .projects import ProjectError, identifier, project_view, utc
from .review_fallbacks import ReviewFallbackService
from .scheduling import SchedulingService
from .tasks import TaskService, content
from .transactions import lock_company


class ReviewService:
    def __init__(self, sessions, now=None):
        self.sessions = sessions
        self.now = now or (lambda: datetime.now(UTC))
        self.tasks = TaskService(sessions)
        self.scheduling = SchedulingService(sessions, self.now)
        self.fallbacks = ReviewFallbackService(sessions, {"ADMIN", "MANAGER"}, self.now)

    def locked(self, session, authority, project_id):
        actor, project, leader, supervisor = self.tasks.scope(session, authority, project_id)
        lock_company(session, actor.issuer)
        session.expire_all()
        current, project, leader, supervisor = self.tasks.scope(session, authority, project_id)
        if current != actor:
            raise ProjectError("task_access_denied", 403)
        return actor, project, leader, supervisor

    def task(self, session, project, task_id):
        row = session.scalar(
            select(WorkTask).where(
                WorkTask.id == identifier(task_id), WorkTask.project_id == project.id
            )
        )
        if not row:
            raise ProjectError("task_not_found", 404)
        return row

    def fallback(self, session, project):
        rows = session.scalars(
            select(ReviewFallback).where(
                ReviewFallback.project_id == project.id,
                ReviewFallback.scope.in_(["REVIEWS", "BOTH"]),
                ReviewFallback.revoked_at.is_(None),
            )
        ).all()
        return next((r for r in rows if self.fallbacks.active(session, r)), None)

    def replay(self, session, request_id, digest, actor, task):
        prior = session.scalar(select(TaskChange).where(TaskChange.request_id == request_id))
        if prior:
            if (
                prior.actor_id != actor.account_id
                or prior.task_id != task.id
                or prior.request_hash != digest
            ):
                raise ProjectError("task_request_conflict")
            return {
                "task_id": task.id,
                "version": prior.task_version,
                "project_version": prior.project_version,
            }
        return None

    def snapshot(self, session, task):
        execution = session.get(TaskExecution, task.id)
        return {
            "status": task.status,
            "progress": execution.progress if execution else 0,
            "blocker": execution.blocker if execution else None,
            "started_at": utc(execution.started_at) if execution else None,
            "completed_at": utc(execution.completed_at)
            if execution and execution.completed_at
            else None,
        }

    def record(self, session, task, project, actor, value, before):
        task.version += 1
        project.version += 1
        session.add(
            TaskChange(
                task_id=task.id,
                request_id=value["request_id"],
                request_hash=fingerprint(value),
                actor_id=actor.account_id,
                actor_name=actor.display_name,
                action=value["action"],
                reason=value["note"],
                before=json.dumps(before, sort_keys=True),
                after=json.dumps(self.snapshot(session, task), sort_keys=True),
                task_version=task.version,
                project_version=project.version,
                created_at=self.now(),
            )
        )
        session.flush()
        return {"task_id": task.id, "version": task.version, "project_version": project.version}

    def advance(self, session, project):
        state = session.get(DeliveryState, project.id)
        advance_schedule(session, project.id, state.schedule_version if state else 0)

    def execute(self, authority, directory, value):
        if (
            set(value)
            != {
                "project_id",
                "task_id",
                "version",
                "project_version",
                "request_id",
                "action",
                "note",
                "progress",
                "blocker",
                "confirm",
            }
            or value["confirm"] is not True
            or value["action"] not in {"START", "PROGRESS", "SUBMIT"}
            or type(value["version"]) is not int
            or type(value["project_version"]) is not int
            or type(value["progress"]) is not int
            or not 0 <= value["progress"] <= 100
            or (value["blocker"] is not None and not isinstance(value["blocker"], str))
        ):
            raise ProjectError("invalid_task_execution", 400)
        value = {
            **value,
            "request_id": identifier(value["request_id"]),
            "note": content(value["note"], 8000),
            "blocker": content(value["blocker"], 2000) if value["blocker"] is not None else None,
        }
        with self.sessions() as session, session.begin():
            actor, project, _, _ = self.locked(session, authority, value["project_id"])
            task = self.task(session, project, value["task_id"])
            assignment = self.tasks.assignment(session, task)
            if (
                actor.role != "EMPLOYEE"
                or not assignment
                or assignment.account_id != actor.account_id
            ):
                raise ProjectError("task_execution_denied", 403)
            self.tasks.member(session, project, actor.account_id, directory)
            prior = self.replay(session, value["request_id"], fingerprint(value), actor, task)
            if prior:
                return prior
            if task.version != value["version"] or project.version != value["project_version"]:
                raise ProjectError("stale_task")
            action = value["action"]
            if action == "START":
                if value["progress"] != 0 or value["blocker"] is not None:
                    raise ProjectError("invalid_task_execution", 400)
                self.scheduling.require_ready_in_transaction(
                    session, authority, project.id, task.id, directory
                )
            elif task.status != "IN_PROGRESS":
                raise ProjectError("task_execution_state")
            execution = session.get(TaskExecution, task.id)
            if action != "START" and not execution:
                raise ProjectError("task_execution_state")
            if action == "SUBMIT" and (
                value["progress"] != execution.progress or value["blocker"] != execution.blocker
            ):
                raise ProjectError("invalid_task_execution", 400)
            before = self.snapshot(session, task)
            self.advance(session, project)
            if action == "START":
                execution = TaskExecution(task_id=task.id, progress=0, started_at=self.now())
                session.add(execution)
                task.status = "IN_PROGRESS"
            elif action == "PROGRESS":
                execution.progress, execution.blocker = value["progress"], value["blocker"]
            else:
                task.status = "AWAITING_REVIEW"
            session.flush()
            receipt = self.record(session, task, project, actor, value, before)
            if action == "SUBMIT":
                plan = session.get(TaskSchedule, task.id)
                snapshot = {
                    **self.snapshot(session, task),
                    "instructions": task.instructions,
                    "acceptance_criteria": task.acceptance_criteria,
                    "schedule": json.loads(plan.current) if plan else None,
                }
                session.add(
                    TaskSubmission(
                        id=str(uuid4()),
                        task_id=task.id,
                        assignment_id=assignment.id,
                        request_id=value["request_id"],
                        submitter_id=actor.account_id,
                        submitter_name=actor.display_name,
                        task_version=task.version,
                        summary=value["note"],
                        snapshot=json.dumps(snapshot, sort_keys=True),
                        submitted_at=self.now(),
                    )
                )
            session.flush()
            return receipt

    def decide(self, authority, directory, value):
        if (
            set(value)
            != {
                "project_id",
                "task_id",
                "submission_id",
                "version",
                "project_version",
                "request_id",
                "outcome",
                "feedback",
                "self_confirm",
                "confirm",
            }
            or value["confirm"] is not True
            or type(value["self_confirm"]) is not bool
            or value["outcome"] not in {"APPROVE", "RETURN"}
            or type(value["version"]) is not int
            or type(value["project_version"]) is not int
        ):
            raise ProjectError("invalid_review", 400)
        value = {
            **value,
            "request_id": identifier(value["request_id"]),
            "feedback": content(value["feedback"], 8000),
        }
        with self.sessions() as session, session.begin():
            actor, project, leader, _ = self.locked(session, authority, value["project_id"])
            task = self.task(session, project, value["task_id"])
            fallback = None
            if not leader:
                fallback = self.fallbacks.require_in_transaction(
                    session, authority, project.id, "REVIEWS"
                )
            submission = session.scalar(
                select(TaskSubmission).where(
                    TaskSubmission.id == identifier(value["submission_id"]),
                    TaskSubmission.task_id == task.id,
                )
            )
            if not submission:
                raise ProjectError("submission_not_found", 404)
            assignment = self.tasks.assignment(session, task)
            if (
                not assignment
                or assignment.id != submission.assignment_id
                or assignment.account_id != submission.submitter_id
            ):
                raise ProjectError("stale_review")
            self.tasks.member(session, project, assignment.account_id, directory)
            own_approval = (
                actor.account_id == submission.submitter_id and value["outcome"] == "APPROVE"
            )
            if value["self_confirm"] != own_approval:
                raise ProjectError(
                    "explicit_self_approval_required" if own_approval else "invalid_review"
                )
            prior = self.replay(session, value["request_id"], fingerprint(value), actor, task)
            if prior:
                return prior
            if (
                submission.closed_at
                or task.status != "AWAITING_REVIEW"
                or task.version != value["version"]
                or task.version != submission.task_version
                or project.version != value["project_version"]
            ):
                raise ProjectError("stale_review")
            execution = session.get(TaskExecution, task.id)
            if not execution:
                raise ProjectError("task_execution_state")
            before = self.snapshot(session, task)
            self.advance(session, project)
            task.status = "COMPLETED" if value["outcome"] == "APPROVE" else "IN_PROGRESS"
            if value["outcome"] == "APPROVE":
                execution.completed_at = self.now()
            submission.closed_at = self.now()
            session.flush()
            receipt = self.record(
                session,
                task,
                project,
                actor,
                {**value, "action": value["outcome"], "note": value["feedback"]},
                before,
            )
            # Replay hashes bind the public decision input, not the audit display adaptation.
            change = session.scalar(
                select(TaskChange).where(TaskChange.request_id == value["request_id"])
            )
            change.request_hash = fingerprint(value)
            session.add(
                TaskReviewDecision(
                    submission_id=submission.id,
                    request_id=value["request_id"],
                    actor_id=actor.account_id,
                    actor_name=actor.display_name,
                    outcome=value["outcome"],
                    feedback=value["feedback"],
                    self_approval=own_approval,
                    fallback_id=fallback["record_id"] if fallback else None,
                    task_version=task.version,
                    project_version=project.version,
                    decided_at=self.now(),
                )
            )
            session.flush()
            return receipt

    def workspace(self, authority, directory, project_id, page=0):
        if type(page) is not int or not 0 <= page <= 10000:
            raise ProjectError("invalid_page", 400)
        with self.sessions() as session:
            actor, project, leader, supervisor = self.tasks.scope(session, authority, project_id)
            fallback = self.fallback(session, project) if manages(actor, project) else None
            can_review = leader or fallback is not None
            tasks = session.scalars(
                select(WorkTask)
                .where(WorkTask.project_id == project.id)
                .order_by(WorkTask.created_at, WorkTask.id)
                .offset(page * 25)
                .limit(26)
            ).all()
            selected = tasks[:25]
            task_ids = [t.id for t in selected]
            assignments = {t.id: self.tasks.assignment(session, t) for t in selected}
            account_ids = sorted({r.account_id for r in assignments.values() if r})
            members = set(
                session.scalars(
                    select(ProjectMember.account_id).where(
                        ProjectMember.project_id == project.id,
                        ProjectMember.issuer == project.issuer,
                        ProjectMember.active.is_(True),
                    )
                )
            )
            candidates = directory(account_ids) if account_ids else []
            eligible_ids = {
                r["account_id"]
                for r in candidates
                if r.get("account_id") in account_ids
                and r.get("active") is True
                and r.get("role") == "EMPLOYEE"
            } & members
            executions = {
                r.task_id: r
                for r in session.scalars(
                    select(TaskExecution).where(TaskExecution.task_id.in_(task_ids))
                )
            }
            ranked = select(
                TaskSubmission.id,
                func.row_number()
                .over(
                    partition_by=TaskSubmission.task_id, order_by=TaskSubmission.task_version.desc()
                )
                .label("position"),
            )
            ranked = ranked.where(TaskSubmission.task_id.in_(task_ids))
            if not supervisor:
                ranked = ranked.where(TaskSubmission.submitter_id == actor.account_id)
            ranked = ranked.subquery()
            submissions = session.scalars(
                select(TaskSubmission)
                .join(ranked, TaskSubmission.id == ranked.c.id)
                .where(ranked.c.position <= 25)
                .order_by(TaskSubmission.task_version.desc())
            ).all()
            decisions = {
                r.submission_id: r
                for r in session.scalars(
                    select(TaskReviewDecision).where(
                        TaskReviewDecision.submission_id.in_([s.id for s in submissions])
                    )
                )
            }
            grouped = {t: [] for t in task_ids}
            for submission in submissions:
                grouped[submission.task_id].append(submission)
            ranked_updates = select(
                TaskChange.id,
                func.row_number()
                .over(partition_by=TaskChange.task_id, order_by=TaskChange.task_version.desc())
                .label("position"),
            )
            ranked_updates = ranked_updates.where(
                TaskChange.task_id.in_(task_ids),
                TaskChange.action.in_(["START", "PROGRESS", "SUBMIT"]),
            )
            if not supervisor:
                ranked_updates = ranked_updates.where(TaskChange.actor_id == actor.account_id)
            ranked_updates = ranked_updates.subquery()
            updates = session.scalars(
                select(TaskChange)
                .join(ranked_updates, TaskChange.id == ranked_updates.c.id)
                .where(ranked_updates.c.position <= 25)
                .order_by(TaskChange.task_version.desc())
            ).all()
            grouped_updates = {t: [] for t in task_ids}
            for update in updates:
                snapshot = json.loads(update.after)
                grouped_updates[update.task_id].append(
                    {
                        "id": update.id,
                        "action": update.action,
                        "note": update.reason,
                        "actor_name": update.actor_name,
                        "created_at": utc(update.created_at),
                        "progress": snapshot["progress"],
                        "blocker": snapshot["blocker"],
                        "status": snapshot["status"],
                    }
                )
            rows = []
            for task in selected:
                assignment = assignments[task.id]
                own = bool(
                    assignment
                    and assignment.account_id == actor.account_id
                    and actor.role == "EMPLOYEE"
                )
                if not supervisor and not own:
                    continue
                eligible = bool(assignment and assignment.account_id in eligible_ids)
                execution = executions.get(task.id)
                submissions = grouped[task.id]
                rows.append(
                    {
                        "id": task.id,
                        "title": task.title,
                        "status": task.status,
                        "version": task.version,
                        "own": own,
                        "can_act": own and eligible,
                        "instructions": task.instructions,
                        "acceptance_criteria": task.acceptance_criteria,
                        "progress": execution.progress if execution else 0,
                        "blocker": execution.blocker if execution else None,
                        "started_at": utc(execution.started_at) if execution else None,
                        "completed_at": utc(execution.completed_at)
                        if execution and execution.completed_at
                        else None,
                        "assignee_name": assignment.display_name if assignment else None,
                        "can_review": can_review and eligible,
                        "work_history": grouped_updates[task.id],
                        "submissions": [
                            self.submission_view(r, decisions.get(r.id))
                            for r in submissions
                            if supervisor or r.submitter_id == actor.account_id
                        ],
                    }
                )
            return {
                "project": project_view(project),
                "is_leader": leader,
                "can_review": can_review,
                "fallback_id": fallback.id if fallback else None,
                "has_more": len(tasks) > 25,
                "tasks": rows,
            }

    def submission_view(self, row, decision):
        return {
            "id": row.id,
            "submitter_name": row.submitter_name,
            "submitted_at": utc(row.submitted_at),
            "version": row.task_version,
            "summary": row.summary,
            "snapshot": row.snapshot,
            "pending": row.closed_at is None,
            "decision": {
                "actor_name": decision.actor_name,
                "outcome": decision.outcome,
                "feedback": decision.feedback,
                "self_approval": decision.self_approval,
                "fallback_id": decision.fallback_id,
                "decided_at": utc(decision.decided_at),
            }
            if decision
            else None,
        }
