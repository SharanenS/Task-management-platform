from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.main import actor_context, failure, require_internal_service
from app.models import Project, ProjectMembership, ProjectRole, ProjectStatus
from app.schemas import ProjectCreateRequest, ProjectUpdateRequest
from app.service import (
    Actor,
    WorkError,
    add_member,
    change_member_role,
    create_project,
    get_project,
    list_projects,
    remove_member,
    set_status,
    update_project,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as value:
        yield value


def actor(role: str = "MANAGER") -> Actor:
    return Actor(uuid4(), role)


def test_internal_credential_is_required() -> None:
    with pytest.raises(HTTPException) as caught:
        require_internal_service("incorrect")
    assert caught.value.status_code == 403


def test_creation_normalizes_key_and_assigns_manager(session: Session) -> None:
    owner = actor()
    project = create_project(session, owner, key="OPS", name="Operations", description=None)
    assert project.key == "OPS"
    assert project.status == ProjectStatus.DRAFT
    assert [(member.employee_id, member.role) for member in project.memberships] == [
        (owner.employee_id, ProjectRole.PROJECT_MANAGER)
    ]


def test_member_cannot_create(session: Session) -> None:
    with pytest.raises(WorkError, match="not permitted") as caught:
        create_project(session, actor("MEMBER"), key="NO", name="Denied", description=None)
    assert caught.value.code == "FORBIDDEN"


def test_project_key_is_unique(session: Session) -> None:
    owner = actor()
    create_project(session, owner, key="ONE", name="One", description=None)
    with pytest.raises(WorkError) as caught:
        create_project(session, owner, key="ONE", name="Two", description=None)
    assert caught.value.code == "PROJECT_KEY_CONFLICT"


def test_access_is_limited_to_members_and_admin(session: Session) -> None:
    owner, outsider = actor(), actor("MEMBER")
    project = create_project(session, owner, key="SEC", name="Secure", description=None)
    with pytest.raises(WorkError) as caught:
        get_project(session, outsider, project.id)
    assert caught.value.code == "FORBIDDEN"
    assert get_project(session, Actor(uuid4(), "ADMIN"), project.id).id == project.id


def test_directory_filters_and_rejects_malformed_cursor(session: Session) -> None:
    owner = actor()
    create_project(session, owner, key="ALPHA", name="Alpha", description=None)
    create_project(session, owner, key="BETA", name="Beta", description=None)
    page = list_projects(session, owner, first=1, after=None, search="alpha", status=None)
    assert [item.key for item in page.items] == ["ALPHA"]
    with pytest.raises(WorkError) as caught:
        list_projects(session, owner, first=10, after="bad", search=None, status=None)
    assert caught.value.code == "INVALID_CURSOR"


def test_lifecycle_and_optimistic_conflict(session: Session) -> None:
    owner = actor()
    project = create_project(session, owner, key="LIFE", name="Lifecycle", description=None)
    project = set_status(
        session, owner, project.id, status=ProjectStatus.ACTIVE, expected_version=1
    )
    with pytest.raises(WorkError) as caught:
        update_project(
            session,
            owner,
            project.id,
            name="Stale",
            description=None,
            expected_version=1,
        )
    assert caught.value.code == "VERSION_CONFLICT"
    project = set_status(
        session, owner, project.id, status=ProjectStatus.ARCHIVED, expected_version=2
    )
    with pytest.raises(WorkError) as archived:
        update_project(
            session,
            owner,
            project.id,
            name="No",
            description=None,
            expected_version=3,
        )
    assert archived.value.code == "PROJECT_ARCHIVED"
    project = set_status(
        session, owner, project.id, status=ProjectStatus.ACTIVE, expected_version=3
    )
    with pytest.raises(WorkError) as invalid:
        set_status(session, owner, project.id, status=ProjectStatus.DRAFT, expected_version=4)
    assert invalid.value.code == "INVALID_STATUS"


def test_membership_rules_and_final_manager(session: Session) -> None:
    owner, contributor = actor(), uuid4()
    project = create_project(session, owner, key="TEAM", name="Team", description=None)
    project = add_member(session, owner, project.id, contributor, ProjectRole.CONTRIBUTOR)
    assert len(project.memberships) == 2
    with pytest.raises(WorkError) as duplicate:
        add_member(session, owner, project.id, contributor, ProjectRole.CONTRIBUTOR)
    assert duplicate.value.code == "MEMBERSHIP_CONFLICT"
    with pytest.raises(WorkError) as final:
        remove_member(session, owner, project.id, owner.employee_id)
    assert final.value.code == "FINAL_PROJECT_MANAGER"
    project = change_member_role(
        session, owner, project.id, contributor, ProjectRole.PROJECT_MANAGER
    )
    project = remove_member(session, owner, project.id, owner.employee_id)
    assert [member.employee_id for member in project.memberships] == [contributor]


def test_contributor_cannot_administer(session: Session) -> None:
    owner = actor()
    contributor = Actor(uuid4(), "MANAGER")
    project = create_project(session, owner, key="READ", name="Read only", description=None)
    add_member(session, owner, project.id, contributor.employee_id, ProjectRole.CONTRIBUTOR)
    with pytest.raises(WorkError) as caught:
        update_project(
            session,
            contributor,
            project.id,
            name="Denied",
            description=None,
            expected_version=1,
        )
    assert caught.value.code == "FORBIDDEN"


@pytest.mark.parametrize("role", ["ADMIN", "MANAGER"])
def test_admin_and_manager_create_draft_with_creator_membership(
    session: Session, role: str
) -> None:
    owner = actor(role)
    project = create_project(
        session, owner, key=f"{role}-PROJECT", name="  Project name  ", description="Details"
    )
    assert project.name == "Project name"
    assert project.status == ProjectStatus.DRAFT
    assert project.version == 1
    assert project.creator_employee_id == owner.employee_id
    assert [(item.employee_id, item.role) for item in project.memberships] == [
        (owner.employee_id, ProjectRole.PROJECT_MANAGER)
    ]


@pytest.mark.parametrize("value", ["", "1BAD", "A B", "A_", "A" * 33])
def test_project_create_schema_rejects_invalid_keys(value: str) -> None:
    with pytest.raises(ValidationError):
        ProjectCreateRequest(key=value, name="Valid project")


def test_project_schemas_normalize_input_and_reject_blank_name() -> None:
    value = ProjectCreateRequest(key="  ops-1 ", name="  Operations   One ")
    assert (value.key, value.name) == ("OPS-1", "Operations One")
    with pytest.raises(ValidationError):
        ProjectUpdateRequest(name="   ", description=None, expected_version=1)


def test_duplicate_normalized_key_is_translated(session: Session) -> None:
    owner = actor()
    first = ProjectCreateRequest(key=" ops ", name="One")
    second = ProjectCreateRequest(key="OPS", name="Two")
    create_project(session, owner, **first.model_dump())
    with pytest.raises(WorkError) as caught:
        create_project(session, owner, **second.model_dump())
    assert caught.value.code == "PROJECT_KEY_CONFLICT"
    assert "sql" not in caught.value.message.lower()


def test_actor_context_rejects_missing_invalid_and_unknown_values() -> None:
    for employee_id, role in [("", "ADMIN"), ("not-a-uuid", "ADMIN"), (str(uuid4()), "OWNER")]:
        with pytest.raises(HTTPException) as caught:
            actor_context(employee_id, role)
        assert caught.value.status_code == 403
        assert caught.value.detail == "Forbidden"


def test_failure_response_contains_only_domain_code_and_message() -> None:
    response = failure(WorkError("CONFLICT", "The request conflicts.", 409))
    assert response.status_code == 409
    assert response.detail == {"code": "CONFLICT", "message": "The request conflicts."}


def test_admin_sees_all_while_members_see_only_assigned_projects(session: Session) -> None:
    first_owner, second_owner = actor(), actor()
    first = create_project(session, first_owner, key="FIRST", name="First", description=None)
    second = create_project(session, second_owner, key="SECOND", name="Second", description=None)
    contributor = actor("MEMBER")
    add_member(session, first_owner, first.id, contributor.employee_id, ProjectRole.CONTRIBUTOR)
    admin_page = list_projects(
        session, actor("ADMIN"), first=50, after=None, search=None, status=None
    )
    assert {item.id for item in admin_page.items} == {first.id, second.id}
    member_page = list_projects(
        session, contributor, first=50, after=None, search=None, status=None
    )
    assert [item.id for item in member_page.items] == [first.id]
    with pytest.raises(WorkError) as caught:
        get_project(session, contributor, second.id)
    assert caught.value.code == "FORBIDDEN"


def test_directory_combines_search_status_ordering_and_forward_pagination(
    session: Session,
) -> None:
    owner = actor()
    alpha = create_project(session, owner, key="OPS-A", name="Operations Alpha", description=None)
    beta = create_project(session, owner, key="OPS-B", name="Operations Beta", description=None)
    create_project(session, owner, key="OTHER", name="Unrelated", description=None)
    set_status(session, owner, beta.id, status=ProjectStatus.ACTIVE, expected_version=1)
    filtered = list_projects(
        session,
        owner,
        first=10,
        after=None,
        search=" operations ",
        status=ProjectStatus.ACTIVE,
    )
    assert [item.id for item in filtered.items] == [beta.id]
    first_page = list_projects(session, owner, first=1, after=None, search="OPS", status=None)
    assert first_page.has_next_page is True
    assert first_page.next_cursor
    second_page = list_projects(
        session, owner, first=1, after=first_page.next_cursor, search="OPS", status=None
    )
    assert second_page.items[0].id != first_page.items[0].id
    assert [item.id for item in first_page.items + second_page.items] == sorted([alpha.id, beta.id])


@pytest.mark.parametrize("size", [0, 51])
def test_directory_rejects_out_of_range_page_size(session: Session, size: int) -> None:
    with pytest.raises(WorkError) as caught:
        list_projects(session, actor(), first=size, after=None, search=None, status=None)
    assert caught.value.code == "INVALID_PAGE_SIZE"


def test_authorized_update_succeeds_and_key_remains_immutable(session: Session) -> None:
    owner = actor()
    project = create_project(session, owner, key="IMMUTABLE", name="Before", description=None)
    updated = update_project(
        session,
        owner,
        project.id,
        name="After",
        description="Changed",
        expected_version=1,
    )
    assert (updated.key, updated.name, updated.description, updated.version) == (
        "IMMUTABLE",
        "After",
        "Changed",
        2,
    )


def test_non_member_and_contributor_updates_are_rejected(session: Session) -> None:
    owner, outsider = actor(), actor("MANAGER")
    contributor = actor("MEMBER")
    project = create_project(session, owner, key="AUTHZ", name="Authorization", description=None)
    add_member(session, owner, project.id, contributor.employee_id, ProjectRole.CONTRIBUTOR)
    for denied in (outsider, contributor):
        with pytest.raises(WorkError) as caught:
            update_project(
                session,
                denied,
                project.id,
                name="Denied",
                description=None,
                expected_version=1,
            )
        assert caught.value.code == "FORBIDDEN"


def test_admin_override_updates_and_governs_unassigned_project(session: Session) -> None:
    owner, admin = actor(), actor("ADMIN")
    project = create_project(session, owner, key="OVERRIDE", name="Before", description=None)
    project = update_project(
        session, admin, project.id, name="After", description=None, expected_version=1
    )
    project = set_status(
        session, admin, project.id, status=ProjectStatus.ACTIVE, expected_version=2
    )
    assert (project.name, project.status) == ("After", ProjectStatus.ACTIVE)


def test_repeated_status_is_idempotent_and_invalid_reverse_is_rejected(session: Session) -> None:
    owner = actor()
    project = create_project(session, owner, key="REPEAT", name="Repeat", description=None)
    project = set_status(
        session, owner, project.id, status=ProjectStatus.ACTIVE, expected_version=1
    )
    same = set_status(session, owner, project.id, status=ProjectStatus.ACTIVE, expected_version=2)
    assert same.version == 2
    with pytest.raises(WorkError) as caught:
        set_status(session, owner, project.id, status=ProjectStatus.DRAFT, expected_version=2)
    assert caught.value.code == "INVALID_STATUS"


def test_contributor_cannot_change_status_and_archived_membership_is_read_only(
    session: Session,
) -> None:
    owner, contributor = actor(), actor("MEMBER")
    project = create_project(session, owner, key="ARCHIVE", name="Archive", description=None)
    add_member(session, owner, project.id, contributor.employee_id, ProjectRole.CONTRIBUTOR)
    with pytest.raises(WorkError) as denied:
        set_status(
            session,
            contributor,
            project.id,
            status=ProjectStatus.ACTIVE,
            expected_version=1,
        )
    assert denied.value.code == "FORBIDDEN"
    project = set_status(
        session, owner, project.id, status=ProjectStatus.ACTIVE, expected_version=1
    )
    project = set_status(
        session, owner, project.id, status=ProjectStatus.ARCHIVED, expected_version=2
    )
    with pytest.raises(WorkError) as archived:
        add_member(session, owner, project.id, uuid4(), ProjectRole.CONTRIBUTOR)
    assert archived.value.code == "PROJECT_ARCHIVED"


def test_membership_role_changes_removal_and_safe_self_removal(session: Session) -> None:
    owner = actor()
    second_manager, contributor = uuid4(), uuid4()
    project = create_project(session, owner, key="MEMBERS", name="Members", description=None)
    add_member(session, owner, project.id, second_manager, ProjectRole.CONTRIBUTOR)
    change_member_role(session, owner, project.id, second_manager, ProjectRole.PROJECT_MANAGER)
    add_member(session, owner, project.id, contributor, ProjectRole.CONTRIBUTOR)
    project = remove_member(session, owner, project.id, contributor)
    assert contributor not in {item.employee_id for item in project.memberships}
    project = remove_member(session, owner, project.id, owner.employee_id)
    assert [item.employee_id for item in project.memberships] == [second_manager]


def test_final_manager_cannot_be_demoted(session: Session) -> None:
    owner = actor()
    project = create_project(session, owner, key="FINAL", name="Final", description=None)
    with pytest.raises(WorkError) as caught:
        change_member_role(
            session,
            owner,
            project.id,
            owner.employee_id,
            ProjectRole.CONTRIBUTOR,
        )
    assert caught.value.code == "FINAL_PROJECT_MANAGER"


def test_duplicate_membership_integrity_error_is_sanitized(session: Session) -> None:
    owner, target = actor(), uuid4()
    project = create_project(session, owner, key="DUP-MEMBER", name="Duplicate", description=None)
    add_member(session, owner, project.id, target, ProjectRole.CONTRIBUTOR)
    with pytest.raises(WorkError) as caught:
        add_member(session, owner, project.id, target, ProjectRole.CONTRIBUTOR)
    assert caught.value.code == "MEMBERSHIP_CONFLICT"
    assert "database" not in caught.value.message.lower()


def test_database_models_do_not_copy_employee_profile_fields() -> None:
    membership_columns = set(ProjectMembership.__table__.columns.keys())
    project_columns = set(Project.__table__.columns.keys())
    forbidden = {"display_name", "email", "username", "active"}
    assert membership_columns.isdisjoint(forbidden)
    assert project_columns.isdisjoint(forbidden)
