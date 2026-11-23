"""Approved acceptance only: future-producer inputs for receipt-owned S10 projects."""

import json
import os
import sys
from datetime import timedelta
from uuid import UUID, uuid5

from project_work.calendar import local_boundary, normalize, timezone_rules, working_hours
from project_work.delivery_inputs import (
    advance_schedule,
    open_escalation,
    record_assessment,
    refresh_escalation,
)
from project_work.models import DeliveryState, OwnerEscalation, Project
from project_work.owner_decisions import OwnerDecisionService
from project_work.projects import latest_calendar
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def main():
    value = json.load(sys.stdin)
    run, project_id = str(UUID(value["runId"])), str(UUID(value["projectId"]))
    if value["action"] not in {"seed", "refresh"}:
        raise ValueError("Unsupported owner fixture action")
    engine = create_engine(os.environ["PROJECT_WORK_DATABASE_URL"], hide_parameters=True)
    if engine.url.host != "project-work-db" or engine.url.database != "taskspace_project_work":
        raise ValueError("Wrong project-work database")
    sessions = sessionmaker(engine)
    with sessions() as session, session.begin():
        project = session.get(Project, project_id)
        if (
            not project
            or project.issuer != "http://127.0.0.1:8180/realms/taskspace-portals"
            or project.creator_id != run
            or project.owner_id != run
            or run not in project.name
        ):
            raise ValueError("Owner fixture project ownership mismatch")
        state = session.get(DeliveryState, project_id)
        if not state:
            advance_schedule(session, project_id, 0)
        state = session.get(DeliveryState, project_id)
        owners = OwnerDecisionService(sessions)
        forecast = owners.current_deadline(session, project) + timedelta(days=2)
        assessment = record_assessment(
            session,
            project_id,
            state.schedule_version,
            project.version,
            "ASSESSED",
            forecast.isoformat(),
            "Owned S10 assessment " + run,
        )
        calendar = latest_calendar(session, project.issuer)
        config = normalize(json.loads(calendar.config))
        candidate = forecast.astimezone(timezone_rules(config["timezone"])).date() + timedelta(
            days=1
        )
        revised_date = None
        for _ in range(366):
            hours = working_hours(config, candidate)
            if hours and local_boundary(candidate, hours["closes"], config["timezone"]) >= forecast:
                revised_date = candidate.isoformat()
                break
            candidate += timedelta(days=1)
        if not revised_date:
            raise ValueError("No owned revision date")
        if value["action"] == "seed":
            rows = {}
            for label in ("revision", "late", "unknown"):
                source = str(uuid5(UUID(run), project_id + ":" + label))
                row = open_escalation(
                    session,
                    project_id,
                    source,
                    assessment.id if label != "unknown" else None,
                    "Owned S10 " + label + " " + run,
                    "Owned acceptance team " + run,
                )
                rows[label] = {"id": row.id, "version": row.version}
            result = {
                "requests": rows,
                "revisedDate": revised_date,
                "projectVersion": project.version,
            }
        else:
            escalation_id = str(UUID(value["escalationId"]))
            row = session.scalar(
                select(OwnerEscalation).where(
                    OwnerEscalation.id == escalation_id, OwnerEscalation.project_id == project_id
                )
            )
            expected_sources = {
                str(uuid5(UUID(run), project_id + ":" + label))
                for label in ("revision", "late", "unknown")
            }
            if not row or row.source_request_id not in expected_sources or run not in row.reason:
                raise ValueError("Owner fixture escalation ownership mismatch")
            refreshed = refresh_escalation(session, project_id, row.id, row.version, assessment.id)
            result = {
                "version": refreshed.version,
                "projectVersion": project.version,
                "forecastAt": forecast.isoformat(),
            }
        print(json.dumps(result))
    engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Scoped owner fixture failed; private details omitted.", file=sys.stderr)
        sys.exit(1)
