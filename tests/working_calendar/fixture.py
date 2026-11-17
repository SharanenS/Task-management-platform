"""Receipt-bound calendar test cleanup; never delete another actor's calendar data."""

import json
import os
import sys
from uuid import UUID

from project_work.models import CalendarPreview, CalendarVersion
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session


def main():
    value = json.load(sys.stdin)
    run = str(UUID(value["runId"]))
    if value["action"] not in {"inspect", "cleanup"}:
        raise ValueError("Invalid action")
    issuer = "http://127.0.0.1:8180/realms/taskspace-portals"
    engine = create_engine(os.environ["PROJECT_WORK_DATABASE_URL"], hide_parameters=True)
    if engine.url.host != "project-work-db" or engine.url.database != "taskspace_project_work":
        raise ValueError("Wrong calendar boundary")
    with Session(engine) as s, s.begin():
        previews = s.scalars(select(CalendarPreview).where(CalendarPreview.actor_id == run)).all()
        versions = s.scalars(select(CalendarVersion).where(CalendarVersion.actor_id == run)).all()
        for row in [*previews, *versions]:
            config = json.loads(row.config)
            if row.issuer != issuer or not any(run in r["label"] for r in config["holidays"]):
                raise ValueError("Calendar ownership mismatch")
        pids = [r.id for r in previews]
        vids = [r.id for r in versions]
        if any(v.preview_id not in pids for v in versions):
            raise ValueError("Version preview ownership mismatch")
        current = s.scalar(
            select(CalendarVersion)
            .where(CalendarVersion.issuer == issuer)
            .order_by(CalendarVersion.number.desc())
            .limit(1)
        )
        result = {
            "currentNumber": current.number if current else 0,
            "versions": [{"id": r.id, "number": r.number} for r in versions],
            "previews": len(previews),
        }
        if value["action"] == "cleanup":
            if s.scalar(
                select(CalendarPreview.id).where(
                    CalendarPreview.base_version_id.in_(vids), CalendarPreview.actor_id != run
                )
            ) or s.scalar(
                select(CalendarVersion.id).where(
                    CalendarVersion.preview_id.in_(pids), CalendarVersion.actor_id != run
                )
            ):
                raise ValueError("Non-owned calendar data references test resources")
            for row in previews:
                row.base_version_id = None
            s.flush()
            s.execute(delete(CalendarVersion).where(CalendarVersion.id.in_(vids)))
            s.execute(delete(CalendarPreview).where(CalendarPreview.id.in_(pids)))
            s.flush()
            s.expire_all()
            if s.scalar(
                select(CalendarVersion.id).where(CalendarVersion.actor_id == run)
            ) or s.scalar(select(CalendarPreview.id).where(CalendarPreview.actor_id == run)):
                raise ValueError("Calendar cleanup incomplete")
            result["cleaned"] = True
        print(json.dumps(result))
    engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Scoped calendar fixture failed; private details omitted.", file=sys.stderr)
        sys.exit(1)
