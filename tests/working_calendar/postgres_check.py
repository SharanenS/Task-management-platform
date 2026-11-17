"""Real calendar publication race, schema parity and exact synthetic-issuer cleanup."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from project_work.calendar import CalendarError
from project_work.models import Base, CalendarPreview, CalendarVersion
from project_work.service import CalendarService
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker


def main():
    engine = create_engine(os.environ["PROJECT_WORK_DATABASE_URL"], hide_parameters=True)
    if engine.url.host != "project-work-db" or engine.url.database != "taskspace_project_work":
        raise ValueError("Wrong work database")
    sessions = sessionmaker(engine)
    with engine.connect() as c:
        assert compare_metadata(MigrationContext.configure(c), Base.metadata) == []
    issuer = "https://calendar-race.invalid/" + str(uuid4())
    actor = str(uuid4())

    def authority():
        return issuer, actor

    config = {
        "timezone": "Etc/UTC",
        "week": [
            {
                "weekday": i,
                "working": i < 6,
                "opens": "09:00" if i < 6 else None,
                "closes": "17:00" if i < 6 else None,
            }
            for i in range(1, 8)
        ],
        "holidays": [{"date": "2099-12-31", "label": "Owned calendar probe " + actor}],
        "exceptions": [],
    }
    service = CalendarService(sessions)
    try:
        previews = [service.preview(authority, config)["preview_id"] for _ in range(2)]
        barrier = Barrier(2)
        requests = [str(uuid4()), str(uuid4())]

        def publish(index):
            barrier.wait(timeout=5)
            try:
                return service.publish(
                    authority,
                    {"request_id": requests[index], "preview_id": previews[index], "confirm": True},
                )["id"]
            except CalendarError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(publish, [0, 1]))
        assert results.count("stale_calendar_preview") == 1
        winner = 0 if results[0] != "stale_calendar_preview" else 1
        assert (
            service.publish(
                authority,
                {"request_id": requests[winner], "preview_id": previews[winner], "confirm": True},
            )["id"]
            == results[winner]
        )
        with sessions() as s:
            rows = s.scalars(select(CalendarVersion).where(CalendarVersion.issuer == issuer)).all()
            assert len(rows) == 1 and rows[0].number == 1
    finally:
        with sessions() as s, s.begin():
            versions = s.scalars(
                select(CalendarVersion).where(CalendarVersion.issuer == issuer)
            ).all()
            previews = s.scalars(
                select(CalendarPreview).where(CalendarPreview.issuer == issuer)
            ).all()
            assert all(r.actor_id == actor and actor in r.config for r in [*versions, *previews])
            for row in previews:
                row.base_version_id = None
            s.flush()
            s.execute(delete(CalendarVersion).where(CalendarVersion.issuer == issuer))
            s.execute(delete(CalendarPreview).where(CalendarPreview.issuer == issuer))
        with sessions() as s:
            assert not s.scalar(select(CalendarVersion.id).where(CalendarVersion.issuer == issuer))
            assert not s.scalar(select(CalendarPreview.id).where(CalendarPreview.issuer == issuer))
        engine.dispose()
    print("Calendar schema, publication race, replay and exact probe cleanup verified.")


if __name__ == "__main__":
    main()
