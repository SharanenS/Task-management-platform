from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from project_work.models import Project, ProjectPreview
from project_work.projects import ProjectActor, ProjectError, ProjectService
from sqlalchemy import select
from working_calendar.test_calendar import config
from working_calendar.test_service import publish
from working_calendar.test_service import setup as setup


@pytest.fixture
def projects(setup):
    calendar, sessions, calendar_actor = setup
    version, _ = publish(calendar, calendar_actor)
    service = ProjectService(sessions)
    manager = ProjectActor(calendar_actor()[0], str(uuid4()), "MANAGER", "Fixture manager")
    return service, sessions, manager, version, calendar, calendar_actor


def create(service, actor, name="Owned project", **fields):
    preview = service.preview(
        lambda: actor,
        {
            "name": name,
            "objectives": "Deliver the agreed result",
            "deadline_date": "2026-11-24",
            **fields,
        },
    )
    command = {"request_id": str(uuid4()), "preview_id": preview["preview_id"], "confirm": True}
    return service.create(lambda: actor, command), command


@pytest.mark.parametrize("role", ["ADMIN", "MANAGER"])
def test_creator_becomes_owner_with_pinned_original_deadline(projects, role):
    service, sessions, manager, version, *_ = projects
    actor = ProjectActor(manager.issuer, manager.account_id, role, manager.display_name)
    result, command = create(service, actor)
    assert result["creator_id"] == result["owner_id"] == actor.account_id
    assert result["creator_name"] == result["owner_name"] == "Fixture manager"
    assert result["calendar_version_id"] == version["id"]
    assert result["deadline_date"] == "2026-11-24"
    assert result["deadline_local"] == "2026-11-24T17:00:00+05:30"
    assert result["approved_deadline"] == "2026-11-24T11:30:00+00:00"
    assert service.create(lambda: actor, command)["id"] == result["id"]
    with sessions() as s:
        assert len(s.scalars(select(Project)).all()) == 1


@pytest.mark.parametrize("role", ["EMPLOYEE", "HR"])
def test_company_roles_do_not_gain_project_operations(projects, role):
    service, sessions, manager, version, *_ = projects
    result, _ = create(service, manager)
    actor = ProjectActor(manager.issuer, str(uuid4()), role, "Denied")
    for action in [
        lambda: service.workspace(lambda: actor),
        lambda: service.detail(lambda: actor, result["id"]),
        lambda: service.preview(lambda: actor, {}),
    ]:
        with pytest.raises(ProjectError) as error:
            action()
        assert error.value.status == 403


def test_manager_scope_search_detail_and_historical_creator_do_not_grant_access(projects):
    service, sessions, manager, version, *_ = projects
    own, _ = create(service, manager)
    other = ProjectActor(manager.issuer, str(uuid4()), "MANAGER", "Other manager")
    unrelated, _ = create(service, other, "Unrelated project")
    assert [p["id"] for p in service.workspace(lambda: manager)["projects"]] == [own["id"]]
    assert service.workspace(lambda: manager, search="Unrelated")["projects"] == []
    for project_id in (unrelated["id"], str(uuid4())):
        with pytest.raises(ProjectError) as error:
            service.detail(lambda: manager, project_id)
        assert error.value.code == "project_not_found"
    with sessions() as s:
        project = s.get(Project, own["id"])
        project.owner_id = other.account_id
        project.owner_name = other.display_name
        s.commit()
    assert service.workspace(lambda: manager)["projects"] == []
    with pytest.raises(ProjectError):
        service.detail(lambda: manager, own["id"])
    details = service.detail(lambda: other, own["id"])
    assert details["creator_id"] == manager.account_id and details["owner_id"] == other.account_id
    admin = ProjectActor(manager.issuer, str(uuid4()), "ADMIN", "Admin")
    assert len(service.workspace(lambda: admin)["projects"]) == 2
    foreign = ProjectActor("https://foreign.invalid", manager.account_id, "ADMIN", "Foreign")
    assert service.workspace(lambda: foreign)["projects"] == []
    with pytest.raises(ProjectError):
        service.detail(lambda: foreign, own["id"])


def test_calendar_required_and_non_working_deadline_is_not_silently_shifted(projects):
    service, sessions, manager, version, *_ = projects
    with pytest.raises(ProjectError) as error:
        create(service, manager, deadline_date="2026-11-22")
    assert error.value.code == "non_working_deadline"
    with pytest.raises(ProjectError) as error:
        create(service, manager, deadline_date="2026-02-29")
    assert error.value.code == "invalid_date"
    foreign = ProjectActor(
        "https://unconfigured.invalid", manager.account_id, "MANAGER", "Unconfigured"
    )
    with pytest.raises(ProjectError) as error:
        create(service, foreign)
    assert error.value.code == "company_calendar_required"
    with sessions() as s:
        assert s.scalars(select(ProjectPreview)).all() == []


def test_calendar_change_stale_preview_and_role_revocation_reject_creation(projects):
    service, sessions, manager, version, calendar, calendar_actor = projects
    preview = service.preview(
        lambda: manager,
        {"name": "Project", "objectives": "Objective", "deadline_date": "2026-11-24"},
    )
    changed = config()
    changed["holidays"] = [{"date": "2026-11-24", "label": "New holiday"}]
    publish(calendar, calendar_actor, changed)
    command = {"preview_id": preview["preview_id"], "request_id": str(uuid4()), "confirm": True}
    with pytest.raises(ProjectError) as error:
        service.create(lambda: manager, command)
    assert error.value.code == "stale_project_calendar"
    revoked = ProjectActor(manager.issuer, manager.account_id, "EMPLOYEE", manager.display_name)
    with pytest.raises(ProjectError) as error:
        service.create(lambda: revoked, command)
    assert error.value.status == 403
    with sessions() as s:
        assert s.scalars(select(Project)).all() == []


def test_deadline_snapshot_unchanged_after_new_calendar_and_no_implicit_revisions(projects):
    service, sessions, manager, version, calendar, calendar_actor = projects
    result, _ = create(service, manager)
    changed = config()
    changed["holidays"] = [{"date": "2026-11-24", "label": "New holiday"}]
    publish(calendar, calendar_actor, changed)
    after = service.detail(lambda: manager, result["id"])
    assert after == result


def test_preview_confirmation_ownership_expiry_and_conflicting_replay(projects):
    service, sessions, manager, version, *_ = projects
    preview = service.preview(
        lambda: manager,
        {"name": "Project", "objectives": "Objective", "deadline_date": "2026-11-24"},
    )
    command = {"preview_id": preview["preview_id"], "request_id": str(uuid4()), "confirm": False}
    with pytest.raises(ProjectError) as error:
        service.create(lambda: manager, command)
    assert error.value.code == "confirmation_required"
    command["confirm"] = True
    other = ProjectActor(manager.issuer, str(uuid4()), "MANAGER", "Other")
    with pytest.raises(ProjectError) as error:
        service.create(lambda: other, command)
    assert error.value.code == "preview_not_owned"
    with sessions() as s:
        s.get(ProjectPreview, preview["preview_id"]).expires_at = datetime.now(UTC) - timedelta(
            seconds=1
        )
        s.commit()
    with pytest.raises(ProjectError) as error:
        service.create(lambda: manager, command)
    assert error.value.code == "preview_expired"
    result, used = create(service, manager)
    with pytest.raises(ProjectError) as error:
        service.create(lambda: manager, {**used, "preview_id": str(uuid4())})
    assert error.value.code == "request_conflict"
