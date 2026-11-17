from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from project_work.calendar import CalendarError
from project_work.models import Base, CalendarPreview, CalendarVersion
from project_work.service import CalendarService
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from .test_calendar import config


@pytest.fixture
def setup():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def fk(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    actor = ("https://fixture.invalid", str(uuid4()))
    service = CalendarService(sessions)
    yield service, sessions, lambda: actor
    engine.dispose()


def publish(service, actor, value=None):
    preview = service.preview(actor, value or config())
    command = {"request_id": str(uuid4()), "preview_id": preview["preview_id"], "confirm": True}
    return service.publish(actor, command), command


def test_unconfigured_workspace_has_no_seeded_calendar(setup):
    service, sessions, actor = setup
    assert service.workspace(actor) == {"current": None, "history": []}


def test_preview_confirmation_immutability_historical_calculation_and_replay(setup):
    service, sessions, actor = setup
    first, command = publish(service, actor)
    assert service.publish(actor, command)["id"] == first["id"]
    changed = config()
    changed["holidays"] = [{"date": "2026-11-23", "label": "New holiday"}]
    second, _ = publish(service, actor, changed)
    assert (first["number"], second["number"]) == (1, 2)
    old = service.calculation(
        actor, {"version_id": first["id"], "start": "2026-11-20", "duration": 3}
    )
    new = service.calculation(
        actor, {"version_id": second["id"], "start": "2026-11-20", "duration": 3}
    )
    assert old["due_local"].startswith("2026-11-24") and new["due_local"].startswith("2026-11-25")
    assert service.publish(actor, command)["id"] == first["id"]
    with sessions() as s:
        assert len(s.scalars(select(CalendarVersion)).all()) == 2


def test_publish_requires_owned_live_preview_and_confirmation(setup):
    service, sessions, actor = setup
    preview = service.preview(actor, config())
    command = {"request_id": str(uuid4()), "preview_id": preview["preview_id"], "confirm": False}
    with pytest.raises(CalendarError) as error:
        service.publish(actor, command)
    assert error.value.code == "confirmation_required"
    command["confirm"] = True
    for other in [
        ("https://fixture.invalid", str(uuid4())),
        ("https://foreign.invalid", actor()[1]),
    ]:
        with pytest.raises(CalendarError) as error:
            service.publish(lambda: other, command)
        assert error.value.code == "preview_not_owned"
    with sessions() as s:
        s.get(CalendarPreview, preview["preview_id"]).expires_at = datetime.now(UTC) - timedelta(
            seconds=1
        )
        s.commit()
    with pytest.raises(CalendarError) as error:
        service.publish(actor, command)
    assert error.value.code == "preview_expired"


def test_competing_preview_stale_and_no_silent_overwrite(setup):
    service, sessions, actor = setup
    first = service.preview(actor, config())
    second = service.preview(actor, config())
    service.publish(
        actor, {"request_id": str(uuid4()), "preview_id": first["preview_id"], "confirm": True}
    )
    with pytest.raises(CalendarError) as error:
        service.publish(
            actor, {"request_id": str(uuid4()), "preview_id": second["preview_id"], "confirm": True}
        )
    assert error.value.code == "stale_calendar_preview"
    with pytest.raises(CalendarError) as error:
        service.preview(actor, config())
    assert error.value.code == "no_calendar_changes"


def test_cross_issuer_version_and_request_reuse_rejected(setup):
    service, sessions, actor = setup
    first, command = publish(service, actor)
    with pytest.raises(CalendarError) as error:
        service.calculation(
            lambda: ("https://other.invalid", actor()[1]),
            {"version_id": first["id"], "start": "2026-11-20", "duration": 1},
        )
    assert error.value.code == "calendar_version_not_found"
    with pytest.raises(CalendarError) as error:
        service.publish(actor, {**command, "preview_id": str(uuid4())})
    assert error.value.code == "request_conflict"


def test_missing_historical_timezone_rules_fail_instead_of_changing_dates(setup):
    service, sessions, actor = setup
    version, _ = publish(service, actor)
    with sessions() as s:
        s.get(CalendarVersion, version["id"]).tzdb_version = "unavailable-fixture-rules"
        s.commit()
    with pytest.raises(CalendarError) as error:
        service.calculation(
            actor, {"version_id": version["id"], "start": "2026-11-20", "duration": 1}
        )
    assert error.value.code == "unsupported_timezone_version"
