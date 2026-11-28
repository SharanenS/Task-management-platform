"""Receipt-bound S7 resource inspection and cleanup; no non-owned rows are removed."""

import json
import os
import sys
from uuid import UUID, uuid5

from project_work.models import (
    CalendarPreview,
    CalendarVersion,
    CoordinationFollowUp,
    CoordinationRecipient,
    CoordinationRecord,
    DeliveryAssessment,
    DeliveryState,
    OwnerDecision,
    OwnerDecisionPreview,
    OwnerEscalation,
    Project,
    ProjectMember,
    ProjectMembershipChange,
    ProjectPreview,
    ReviewFallback,
    ScheduleChange,
    SchedulePreview,
    TaskAssignment,
    TaskChange,
    TaskDependency,
    TaskSchedule,
    WorkTask,
)
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session


def task_rows(session, project_ids, actors):
    tasks = session.scalars(
        select(WorkTask).where(
            WorkTask.project_id.in_(project_ids) | WorkTask.creator_id.in_(actors)
        )
    ).all()
    if any(row.project_id not in project_ids or row.creator_id not in actors for row in tasks):
        raise ValueError("Task fixture ownership mismatch")
    task_ids = [row.id for row in tasks]
    assignments = session.scalars(
        select(TaskAssignment).where(
            TaskAssignment.task_id.in_(task_ids)
            | TaskAssignment.actor_id.in_(actors)
            | TaskAssignment.account_id.in_(actors)
        )
    ).all()
    if any(
        row.task_id not in task_ids or row.actor_id not in actors or row.account_id not in actors
        for row in assignments
    ):
        raise ValueError("Task assignment fixture ownership mismatch")
    changes = session.scalars(
        select(TaskChange).where(TaskChange.task_id.in_(task_ids) | TaskChange.actor_id.in_(actors))
    ).all()
    if any(row.task_id not in task_ids or row.actor_id not in actors for row in changes):
        raise ValueError("Task history fixture ownership mismatch")
    return {TaskChange: changes, TaskAssignment: assignments, WorkTask: tasks}


def schedule_rows(session, project_ids, actors):
    tasks = task_rows(session, project_ids, actors)[WorkTask]
    ids = [row.id for row in tasks]
    changes = session.scalars(
        select(ScheduleChange).where(
            ScheduleChange.project_id.in_(project_ids) | ScheduleChange.actor_id.in_(actors)
        )
    ).all()
    previews = session.scalars(
        select(SchedulePreview).where(
            SchedulePreview.project_id.in_(project_ids) | SchedulePreview.actor_id.in_(actors)
        )
    ).all()
    if any(
        row.project_id not in project_ids or row.actor_id not in actors
        for row in changes + previews
    ):
        raise ValueError("Schedule fixture ownership mismatch")
    preview_ids = {row.id for row in previews}
    if any(row.preview_id not in preview_ids for row in changes):
        raise ValueError("Schedule preview ownership mismatch")
    edges = session.scalars(
        select(TaskDependency).where(
            TaskDependency.task_id.in_(ids) | TaskDependency.prerequisite_id.in_(ids)
        )
    ).all()
    if any(row.task_id not in ids or row.prerequisite_id not in ids for row in edges):
        raise ValueError("Schedule dependency ownership mismatch")
    plans = session.scalars(select(TaskSchedule).where(TaskSchedule.task_id.in_(ids))).all()
    for row in plans:
        task = next(task for task in tasks if task.id == row.task_id)
        if row.calendar_version_id != session.get(Project, task.project_id).calendar_version_id:
            raise ValueError("Schedule calendar ownership mismatch")
    return {
        ScheduleChange: changes,
        SchedulePreview: previews,
        TaskDependency: edges,
        TaskSchedule: plans,
    }


def owner_rows(session, project_ids, actors, run):
    assessments = session.scalars(
        select(DeliveryAssessment).where(DeliveryAssessment.project_id.in_(project_ids))
    ).all()
    scheduled = session.scalars(
        select(ScheduleChange).where(
            ScheduleChange.project_id.in_(project_ids), ScheduleChange.actor_id.in_(actors)
        )
    ).all()
    if any(
        run not in row.summary
        and not (
            row.summary == "Dependency schedule; capacity is not guaranteed."
            and any(
                c.project_id == row.project_id
                and c.schedule_version == row.schedule_version
                and c.project_version == row.project_version
                for c in scheduled
            )
        )
        for row in assessments
    ):
        raise ValueError("Owner assessment fixture ownership mismatch")
    assessment_ids = [row.id for row in assessments]
    escalations = session.scalars(
        select(OwnerEscalation).where(
            OwnerEscalation.project_id.in_(project_ids)
            | OwnerEscalation.assessment_id.in_(assessment_ids)
        )
    ).all()
    if any(
        row.project_id not in project_ids or run not in row.reason or run not in row.affected_team
        for row in escalations
    ):
        raise ValueError("Owner escalation fixture ownership mismatch")
    escalation_ids = [row.id for row in escalations]
    previews = session.scalars(
        select(OwnerDecisionPreview).where(
            OwnerDecisionPreview.project_id.in_(project_ids)
            | OwnerDecisionPreview.actor_id.in_(actors)
            | OwnerDecisionPreview.escalation_id.in_(escalation_ids)
            | OwnerDecisionPreview.assessment_id.in_(assessment_ids)
        )
    ).all()
    if any(
        row.project_id not in project_ids
        or row.actor_id not in actors
        or row.escalation_id not in escalation_ids
        or row.assessment_id not in assessment_ids
        for row in previews
    ):
        raise ValueError("Owner preview fixture ownership mismatch")
    preview_ids = [row.id for row in previews]
    decisions = session.scalars(
        select(OwnerDecision).where(
            OwnerDecision.project_id.in_(project_ids)
            | OwnerDecision.actor_id.in_(actors)
            | OwnerDecision.escalation_id.in_(escalation_ids)
            | OwnerDecision.assessment_id.in_(assessment_ids)
            | OwnerDecision.preview_id.in_(preview_ids)
        )
    ).all()
    if any(
        row.project_id not in project_ids
        or row.actor_id not in actors
        or row.escalation_id not in escalation_ids
        or (row.assessment_id and row.assessment_id not in assessment_ids)
        or (row.preview_id and row.preview_id not in preview_ids)
        for row in decisions
    ):
        raise ValueError("Owner decision fixture ownership mismatch")
    fallbacks = session.scalars(
        select(ReviewFallback).where(
            ReviewFallback.project_id.in_(project_ids)
            | ReviewFallback.actor_id.in_(actors)
            | ReviewFallback.leader_id.in_(actors)
            | ReviewFallback.revoked_by.in_(actors)
        )
    ).all()
    if any(
        row.project_id not in project_ids
        or row.actor_id not in actors
        or (row.leader_id and row.leader_id not in actors)
        or (row.revoked_by and row.revoked_by not in actors)
        for row in fallbacks
    ):
        raise ValueError("Fallback fixture ownership mismatch")
    states = session.scalars(
        select(DeliveryState).where(DeliveryState.project_id.in_(project_ids))
    ).all()
    return {
        OwnerDecision: decisions,
        OwnerDecisionPreview: previews,
        OwnerEscalation: escalations,
        DeliveryAssessment: assessments,
        DeliveryState: states,
        ReviewFallback: fallbacks,
    }


def main():
    value = json.load(sys.stdin)
    run = str(UUID(value["runId"]))
    if value["action"] not in {"inspect", "cleanup"}:
        raise ValueError("Invalid fixture action")
    actors = {run, str(uuid5(UUID(run), "project-account"))}
    if value.get("peerSubject") is not None:
        UUID(value["peerSubject"])
        actors.add(str(uuid5(UUID(run), "task-peer-account")))
    issuer = "http://127.0.0.1:8180/realms/taskspace-portals"
    engine = create_engine(os.environ["PROJECT_WORK_DATABASE_URL"], hide_parameters=True)
    if engine.url.host != "project-work-db" or engine.url.database != "taskspace_project_work":
        raise ValueError("Wrong work boundary")
    with Session(engine) as s, s.begin():
        projects = s.scalars(select(Project).where(Project.creator_id.in_(actors))).all()
        previews = s.scalars(
            select(ProjectPreview).where(ProjectPreview.actor_id.in_(actors))
        ).all()
        versions = s.scalars(
            select(CalendarVersion).where(CalendarVersion.actor_id.in_(actors))
        ).all()
        calendar_previews = s.scalars(
            select(CalendarPreview).where(CalendarPreview.actor_id.in_(actors))
        ).all()
        for row in [*projects, *previews]:
            if row.issuer != issuer or run not in row.name:
                raise ValueError("Project fixture ownership mismatch")
        if any(row.owner_id not in actors for row in projects):
            raise ValueError("Project owner changed")
        for row in [*versions, *calendar_previews]:
            if row.issuer != issuer or not any(
                run in h["label"] for h in json.loads(row.config)["holidays"]
            ):
                raise ValueError("Calendar fixture ownership mismatch")
        project_ids = [r.id for r in projects]
        preview_ids = [r.id for r in previews]
        version_ids = [r.id for r in versions]
        calendar_ids = [r.id for r in calendar_previews]
        if any(row.preview_id not in preview_ids for row in projects) or any(
            row.preview_id not in calendar_ids for row in versions
        ):
            raise ValueError("Fixture preview ownership mismatch")
        members = s.scalars(
            select(ProjectMember).where(
                ProjectMember.project_id.in_(project_ids) | ProjectMember.account_id.in_(actors)
            )
        ).all()
        changes = s.scalars(
            select(ProjectMembershipChange).where(
                ProjectMembershipChange.project_id.in_(project_ids)
                | ProjectMembershipChange.actor_id.in_(actors)
                | ProjectMembershipChange.target_id.in_(actors)
            )
        ).all()
        if any(
            r.issuer != issuer or r.project_id not in project_ids or r.account_id not in actors
            for r in members
        ):
            raise ValueError("Membership fixture ownership mismatch")
        if any(
            r.issuer != issuer
            or r.project_id not in project_ids
            or r.actor_id not in actors
            or r.target_id not in actors
            for r in changes
        ):
            raise ValueError("Membership history ownership mismatch")
        coordination = s.scalars(
            select(CoordinationRecord).where(
                CoordinationRecord.project_id.in_(project_ids)
                | CoordinationRecord.actor_id.in_(actors)
            )
        ).all()
        if any(
            r.issuer != issuer or r.project_id not in project_ids or r.actor_id not in actors
            for r in coordination
        ):
            raise ValueError("Coordination fixture ownership mismatch")
        coordination_ids = [r.id for r in coordination]
        recipients = s.scalars(
            select(CoordinationRecipient).where(
                CoordinationRecipient.record_id.in_(coordination_ids)
                | CoordinationRecipient.account_id.in_(actors)
            )
        ).all()
        follow_ups = s.scalars(
            select(CoordinationFollowUp).where(
                CoordinationFollowUp.record_id.in_(coordination_ids)
                | CoordinationFollowUp.actor_id.in_(actors)
            )
        ).all()
        if any(
            r.record_id not in coordination_ids or r.account_id not in actors for r in recipients
        ):
            raise ValueError("Coordination recipient ownership mismatch")
        if any(r.record_id not in coordination_ids or r.actor_id not in actors for r in follow_ups):
            raise ValueError("Coordination follow-up ownership mismatch")
        task_data = task_rows(s, project_ids, actors)
        schedule_data = schedule_rows(s, project_ids, actors)
        owner_data = owner_rows(s, project_ids, actors, run)
        result = {
            "scheduleRows": sum(len(rows) for rows in schedule_data.values()),
            "taskRows": sum(len(rows) for rows in task_data.values()),
            "ownerRows": sum(len(rows) for rows in owner_data.values()),
            "coordinationRecords": len(coordination),
            "coordinationRecipients": len(recipients),
            "coordinationFollowUps": len(follow_ups),
            "memberships": len(members),
            "membershipChanges": len(changes),
            "projects": len(projects),
            "previews": len(previews),
            "versions": len(versions),
            "calendarPreviews": len(calendar_previews),
        }
        if value["action"] == "cleanup":
            if s.scalar(
                select(OwnerDecisionPreview.id).where(
                    OwnerDecisionPreview.calendar_version_id.in_(version_ids),
                    OwnerDecisionPreview.project_id.not_in(project_ids),
                )
            ):
                raise ValueError("Foreign owner preview references fixture calendar")
            if s.scalar(
                select(Project.id).where(
                    Project.preview_id.in_(preview_ids), Project.creator_id.not_in(actors)
                )
            ):
                raise ValueError("Foreign project references owned preview")
            if s.scalar(
                select(Project.id).where(
                    Project.calendar_version_id.in_(version_ids), Project.creator_id.not_in(actors)
                )
            ) or s.scalar(
                select(ProjectPreview.id).where(
                    ProjectPreview.calendar_version_id.in_(version_ids),
                    ProjectPreview.actor_id.not_in(actors),
                )
            ):
                raise ValueError("Foreign project references fixture calendar")
            if s.scalar(
                select(CalendarPreview.id).where(
                    CalendarPreview.base_version_id.in_(version_ids),
                    CalendarPreview.actor_id.not_in(actors),
                )
            ) or s.scalar(
                select(CalendarVersion.id).where(
                    CalendarVersion.preview_id.in_(calendar_ids),
                    CalendarVersion.actor_id.not_in(actors),
                )
            ):
                raise ValueError("Foreign calendar references fixture data")
            if s.scalar(
                select(TaskSchedule.task_id).where(
                    TaskSchedule.calendar_version_id.in_(version_ids),
                    TaskSchedule.task_id.not_in([r.id for r in task_data[WorkTask]]),
                )
            ):
                raise ValueError("Foreign task schedule references fixture calendar")
            for model, rows in schedule_data.items():
                if model is TaskDependency:
                    for row in rows:
                        s.execute(
                            delete(model).where(
                                model.task_id == row.task_id,
                                model.prerequisite_id == row.prerequisite_id,
                            )
                        )
                else:
                    key = model.task_id if model is TaskSchedule else model.id
                    s.execute(
                        delete(model).where(
                            key.in_(
                                [row.task_id if model is TaskSchedule else row.id for row in rows]
                            )
                        )
                    )
            s.flush()
            if any(schedule_rows(s, project_ids, actors).values()):
                raise ValueError("Schedule fixture cleanup incomplete")
            for model, rows in task_data.items():
                s.execute(delete(model).where(model.id.in_([r.id for r in rows])))
            s.flush()
            s.expire_all()
            if any(task_rows(s, project_ids, actors).values()):
                raise ValueError("Task fixture cleanup incomplete")
            for model, rows in owner_data.items():
                key = model.project_id if model is DeliveryState else model.id
                s.execute(
                    delete(model).where(
                        key.in_(
                            [row.project_id if model is DeliveryState else row.id for row in rows]
                        )
                    )
                )
            s.flush()
            if any(owner_rows(s, project_ids, actors, run).values()):
                raise ValueError("Owner fixture cleanup incomplete")
            s.execute(
                delete(CoordinationFollowUp).where(
                    CoordinationFollowUp.id.in_([r.id for r in follow_ups])
                )
            )
            s.execute(
                delete(CoordinationRecipient).where(
                    CoordinationRecipient.id.in_([r.id for r in recipients])
                )
            )
            s.execute(delete(CoordinationRecord).where(CoordinationRecord.id.in_(coordination_ids)))
            s.execute(
                delete(ProjectMembershipChange).where(
                    ProjectMembershipChange.id.in_([r.id for r in changes])
                )
            )
            s.execute(delete(ProjectMember).where(ProjectMember.id.in_([r.id for r in members])))
            s.execute(delete(Project).where(Project.id.in_(project_ids)))
            s.execute(delete(ProjectPreview).where(ProjectPreview.id.in_(preview_ids)))
            for row in calendar_previews:
                row.base_version_id = None
            s.flush()
            s.execute(delete(CalendarVersion).where(CalendarVersion.id.in_(version_ids)))
            s.execute(delete(CalendarPreview).where(CalendarPreview.id.in_(calendar_ids)))
            s.flush()
            s.expire_all()
            if (
                s.scalar(
                    select(CoordinationRecord.id).where(
                        CoordinationRecord.project_id.in_(project_ids)
                        | CoordinationRecord.actor_id.in_(actors)
                    )
                )
                or s.scalar(
                    select(CoordinationRecipient.id).where(
                        CoordinationRecipient.record_id.in_(coordination_ids)
                        | CoordinationRecipient.account_id.in_(actors)
                    )
                )
                or s.scalar(
                    select(CoordinationFollowUp.id).where(
                        CoordinationFollowUp.record_id.in_(coordination_ids)
                        | CoordinationFollowUp.actor_id.in_(actors)
                    )
                )
                or s.scalar(
                    select(ProjectMember.id).where(
                        ProjectMember.project_id.in_(project_ids)
                        | ProjectMember.account_id.in_(actors)
                    )
                )
                or s.scalar(
                    select(ProjectMembershipChange.id).where(
                        ProjectMembershipChange.project_id.in_(project_ids)
                        | ProjectMembershipChange.actor_id.in_(actors)
                        | ProjectMembershipChange.target_id.in_(actors)
                    )
                )
                or s.scalar(select(Project.id).where(Project.creator_id.in_(actors)))
                or s.scalar(select(ProjectPreview.id).where(ProjectPreview.actor_id.in_(actors)))
                or s.scalar(select(CalendarVersion.id).where(CalendarVersion.actor_id.in_(actors)))
                or s.scalar(select(CalendarPreview.id).where(CalendarPreview.actor_id.in_(actors)))
            ):
                raise ValueError("Project cleanup incomplete")
            result["cleaned"] = True
        print(json.dumps(result))
    engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Scoped project fixture failed; private details omitted.", file=sys.stderr)
        sys.exit(1)
