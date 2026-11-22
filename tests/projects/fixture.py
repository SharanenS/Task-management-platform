"""Receipt-bound S7 resource inspection and cleanup; no non-owned rows are removed."""

import json
import os
import sys
from uuid import UUID, uuid5

from project_work.models import (
    CalendarPreview,
    CalendarVersion,
    Project,
    ProjectMember,
    ProjectMembershipChange,
    ProjectPreview,
)
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session


def main():
    value = json.load(sys.stdin)
    run = str(UUID(value["runId"]))
    if value["action"] not in {"inspect", "cleanup"}:
        raise ValueError("Invalid fixture action")
    actors = {run, str(uuid5(UUID(run), "project-account"))}
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
        result = {
            "memberships": len(members),
            "membershipChanges": len(changes),
            "projects": len(projects),
            "previews": len(previews),
            "versions": len(versions),
            "calendarPreviews": len(calendar_previews),
        }
        if value["action"] == "cleanup":
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
