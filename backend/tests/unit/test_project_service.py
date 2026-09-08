"""Unit tests for ProjectService and ProjectRepository."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import ProjectStatus
from app.core.exceptions import NotFoundError
from app.models.project import Project
from app.repositories.project import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.project import ProjectService


@pytest.fixture
def mock_repo():
    return AsyncMock(spec=ProjectRepository)


@pytest.fixture
def service(mock_repo):
    return ProjectService(repository=mock_repo)


@pytest.fixture
def sample_project():
    return Project(
        id=uuid.uuid4(),
        name="Enterprise Workflow",
        description="Phase 4 implementation",
        status=ProjectStatus.PLANNING,
        owner_id="keycloak-user-123",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_create_project_success(service, mock_repo):
    data = ProjectCreate(
        name="  New Project  ",
        description="  Some description  ",
        status=ProjectStatus.ACTIVE,
    )
    owner_id = "user-sub-abc"

    created_project = Project(
        id=uuid.uuid4(),
        name="New Project",
        description="Some description",
        status=ProjectStatus.ACTIVE,
        owner_id=owner_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_repo.create.return_value = created_project

    result = await service.create_project(data=data, owner_id=owner_id)

    assert result.name == "New Project"
    assert result.description == "Some description"
    assert result.status == ProjectStatus.ACTIVE
    assert result.owner_id == owner_id
    mock_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_get_project_found(service, mock_repo, sample_project):
    mock_repo.get_by_id.return_value = sample_project

    result = await service.get_project(sample_project.id)

    assert result == sample_project
    mock_repo.get_by_id.assert_called_once_with(sample_project.id)


@pytest.mark.asyncio
async def test_get_project_not_found_raises(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    random_id = uuid.uuid4()

    with pytest.raises(NotFoundError) as exc_info:
        await service.get_project(random_id)

    assert f"Project with ID '{random_id}' not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_list_projects(service, mock_repo, sample_project):
    mock_repo.list_all.return_value = [sample_project]

    result = await service.list_projects()

    assert len(result) == 1
    assert result[0] == sample_project
    mock_repo.list_all.assert_called_once()


@pytest.mark.asyncio
async def test_update_project_success(service, mock_repo, sample_project):
    mock_repo.get_by_id.return_value = sample_project
    mock_repo.update.return_value = sample_project

    update_data = ProjectUpdate(
        name="  Updated Name  ",
        status=ProjectStatus.COMPLETED,
    )

    result = await service.update_project(sample_project.id, update_data)

    assert result.name == "Updated Name"
    assert result.status == ProjectStatus.COMPLETED
    mock_repo.update.assert_called_once_with(sample_project)


@pytest.mark.asyncio
async def test_update_project_not_found(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    random_id = uuid.uuid4()

    with pytest.raises(NotFoundError):
        await service.update_project(random_id, ProjectUpdate(name="New"))


@pytest.mark.asyncio
async def test_delete_project_success(service, mock_repo, sample_project):
    mock_repo.get_by_id.return_value = sample_project
    mock_repo.delete.return_value = None

    await service.delete_project(sample_project.id)

    mock_repo.delete.assert_called_once_with(sample_project)


@pytest.mark.asyncio
async def test_delete_project_not_found(service, mock_repo):
    mock_repo.get_by_id.return_value = None
    random_id = uuid.uuid4()

    with pytest.raises(NotFoundError):
        await service.delete_project(random_id)


# ── Schema Whitespace Validation Tests ───────────────────────────────────────

def test_project_create_whitespace_only_name_rejected():
    """Whitespace-only ProjectCreate name is rejected at schema boundary."""
    with pytest.raises(Exception) as exc_info:
        ProjectCreate(name="   ")
    assert "blank" in str(exc_info.value).lower() or "valid" in str(exc_info.value).lower()


def test_project_create_tab_only_name_rejected():
    """Tab-only ProjectCreate name is rejected at schema boundary."""
    with pytest.raises(Exception):
        ProjectCreate(name="\t")


def test_project_create_newline_only_name_rejected():
    """Newline-only ProjectCreate name is rejected at schema boundary."""
    with pytest.raises(Exception):
        ProjectCreate(name="\n")


def test_project_update_whitespace_only_name_rejected():
    """Whitespace-only ProjectUpdate name is rejected at schema boundary."""
    with pytest.raises(Exception) as exc_info:
        ProjectUpdate(name="   ")
    assert "blank" in str(exc_info.value).lower() or "valid" in str(exc_info.value).lower()


def test_project_update_tab_only_name_rejected():
    """Tab-only ProjectUpdate name is rejected at schema boundary."""
    with pytest.raises(Exception):
        ProjectUpdate(name="\t")


def test_project_create_valid_name_trimmed():
    """Surrounding whitespace on a valid name is stripped successfully."""
    schema = ProjectCreate(name="  Enterprise Platform  ")
    assert schema.name == "Enterprise Platform"


def test_project_update_valid_name_trimmed():
    """Surrounding whitespace on a valid ProjectUpdate name is stripped successfully."""
    schema = ProjectUpdate(name="  Updated Name  ")
    assert schema.name == "Updated Name"


def test_project_update_none_name_accepted():
    """ProjectUpdate with name=None (not provided) is accepted."""
    schema = ProjectUpdate(name=None)
    assert schema.name is None
