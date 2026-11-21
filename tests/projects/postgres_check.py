"""Real project commitment races and rollback-scoped synthetic company cleanup."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from project_work.models import Base, CalendarPreview, CalendarVersion, Project, ProjectPreview
from project_work.projects import ProjectActor, ProjectError, ProjectService
from project_work.service import CalendarService
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker


def main():
    engine = create_engine(os.environ["PROJECT_WORK_DATABASE_URL"], hide_parameters=True)
    if engine.url.host != "project-work-db" or engine.url.database != "taskspace_project_work":
        raise ValueError("Wrong project database")
    sessions = sessionmaker(engine)
    with engine.connect() as c:
        assert compare_metadata(MigrationContext.configure(c), Base.metadata) == []
    issuer = "https://project-race.invalid/" + str(uuid4())
    account = str(uuid4())
    actor = ProjectActor(issuer, account, "MANAGER", "Owned project probe")

    def author():
        return actor

    def admin():
        return issuer, account

    calendars = CalendarService(sessions)
    projects = ProjectService(sessions)
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
        "holidays": [],
        "exceptions": [],
    }
    try:
        cp = calendars.preview(admin, config)
        version = calendars.publish(
            admin, {"preview_id": cp["preview_id"], "request_id": str(uuid4()), "confirm": True}
        )
        pp = projects.preview(
            author,
            {
                "name": "Owned project probe " + account,
                "objectives": "Owned commitment",
                "deadline_date": "2030-01-07",
            },
        )
        requests = [str(uuid4()), str(uuid4())]
        barrier = Barrier(2)

        def create(index):
            barrier.wait(timeout=5)
            try:
                return projects.create(
                    author,
                    {
                        "preview_id": pp["preview_id"],
                        "request_id": requests[index],
                        "confirm": True,
                    },
                )["id"]
            except ProjectError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(create, [0, 1]))
        assert results.count("preview_already_used") == 1
        winner = 0 if results[0] != "preview_already_used" else 1
        assert (
            projects.create(
                author,
                {"preview_id": pp["preview_id"], "request_id": requests[winner], "confirm": True},
            )["id"]
            == results[winner]
        )
        second = projects.preview(
            author,
            {
                "name": "Owned project probe second " + account,
                "objectives": "Pinned calendar",
                "deadline_date": "2030-01-07",
            },
        )
        config["holidays"] = [{"date": "2030-01-07", "label": "Owned calendar change"}]
        changed = calendars.preview(admin, config)
        barrier = Barrier(2)

        def race(which):
            barrier.wait(timeout=5)
            if which == 0:
                return calendars.publish(
                    admin,
                    {
                        "request_id": str(uuid4()),
                        "preview_id": changed["preview_id"],
                        "confirm": True,
                    },
                )["id"]
            try:
                return projects.create(
                    author,
                    {
                        "request_id": str(uuid4()),
                        "preview_id": second["preview_id"],
                        "confirm": True,
                    },
                )["id"]
            except ProjectError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcome = list(pool.map(race, [0, 1]))
        assert outcome[0] not in {"stale_project_calendar", "preview_already_used"}
        if outcome[1] != "stale_project_calendar":
            assert projects.detail(author, outcome[1])["calendar_version_id"] == version["id"]
        assert projects.detail(author, results[winner])["calendar_version_id"] == version["id"]
        with sessions() as s:
            assert all(
                r.creator_id == account and r.owner_id == account
                for r in s.scalars(select(Project).where(Project.issuer == issuer))
            )
    finally:
        with sessions() as s, s.begin():
            rows = s.scalars(select(Project).where(Project.issuer == issuer)).all()
            previews = s.scalars(
                select(ProjectPreview).where(ProjectPreview.issuer == issuer)
            ).all()
            cvs = s.scalars(select(CalendarVersion).where(CalendarVersion.issuer == issuer)).all()
            cps = s.scalars(select(CalendarPreview).where(CalendarPreview.issuer == issuer)).all()
            assert all(
                r.creator_id == account
                and r.owner_id == account
                and r.name.startswith("Owned project probe")
                for r in rows
            )
            assert all(
                r.actor_id == account and r.name.startswith("Owned project probe") for r in previews
            )
            assert all(r.actor_id == account for r in [*cvs, *cps])
            s.execute(delete(Project).where(Project.issuer == issuer))
            s.execute(delete(ProjectPreview).where(ProjectPreview.issuer == issuer))
            for row in cps:
                row.base_version_id = None
            s.flush()
            s.execute(delete(CalendarVersion).where(CalendarVersion.issuer == issuer))
            s.execute(delete(CalendarPreview).where(CalendarPreview.issuer == issuer))
        with sessions() as s:
            for model in [Project, ProjectPreview, CalendarVersion, CalendarPreview]:
                assert not s.scalar(select(model.id).where(model.issuer == issuer))
        engine.dispose()
    print("Project schema, commitment/calendar races, replay and owned cleanup verified.")


if __name__ == "__main__":
    main()
