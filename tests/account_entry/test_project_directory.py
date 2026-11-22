from uuid import uuid4

import pytest
from people.access import AccessDenied, resolve_actor
from people.models import Account, EmployeeProfile
from people.project_directory import ProjectDirectory
from taskspace_security.tokens import Identity
from test_access import ISSUER, provision
from test_access import sessions as sessions
from test_api import SETTINGS
from test_api import boundary as boundary


@pytest.mark.parametrize("role", ["ADMIN", "MANAGER"])
def test_minimal_eligible_directory_and_exact_target_lookup(sessions, role):
    with sessions() as s:
        author = provision(s, role=role)
        employee = provision(s)
        account_id = resolve_actor(s, employee).account_id
        for options in (
            {"role": "HR"},
            {"role": "MANAGER"},
            {"active": False},
            {"profile_active": False},
            {"profile": False},
        ):
            provision(s, **options)
        s.add(EmployeeProfile(issuer=ISSUER, display_name="Directory only", active=True))
        other = Account(issuer="https://other.invalid", subject=str(uuid4()))
        s.add(other)
        s.commit()
        other_id = other.id
    directory = ProjectDirectory(sessions)
    rows = directory.lookup(author)["candidates"]
    assert len(rows) == 1 and rows[0]["account_id"] == account_id
    assert set(rows[0]) == {"account_id", "display_name", "active", "role"}
    assert directory.lookup(author, account_id) == rows[0]
    assert directory.lookup(author, str(uuid4()))["active"] is False
    assert directory.lookup(author, other_id)["active"] is False


@pytest.mark.parametrize("role", ["EMPLOYEE", "HR"])
def test_non_author_cannot_enumerate_appointment_candidates(sessions, role):
    with sessions() as s:
        identity = provision(s, role=role)
    with pytest.raises(AccessDenied):
        ProjectDirectory(sessions).lookup(identity)


def test_directory_rechecks_inactive_and_cross_issuer_actor(sessions):
    with sessions() as s:
        identity = provision(s, role="MANAGER")
        account_id = resolve_actor(s, identity).account_id
    directory = ProjectDirectory(sessions)
    with pytest.raises(AccessDenied):
        directory.lookup(Identity("https://other.invalid", identity.subject))
    with sessions() as s, s.begin():
        s.get(Account, account_id).active = False
    with pytest.raises(AccessDenied):
        directory.lookup(identity)


def test_private_candidate_endpoint_authenticates_and_rechecks_current_role(boundary):
    people, _, sessions, identity = boundary
    auth = {"Authorization": "Bearer valid-provider-token"}
    assert people.get("/internal/project-candidates", headers=auth).status_code == 401
    auth.update({"X-Service-Key": SETTINGS.service_key, "X-Actor-Role": "ADMIN"})
    assert people.get("/internal/project-candidates", headers=auth).status_code == 403
    with sessions() as s:
        account_id = resolve_actor(s, identity).account_id
        s.get(Account, account_id).grants[0].role = "MANAGER"
        employee = provision(s)
        employee_id = resolve_actor(s, employee).account_id
    response = people.get("/internal/project-candidates", headers=auth)
    assert response.status_code == 200
    assert response.json()["candidates"][0]["account_id"] == employee_id
    assert set(response.json()["candidates"][0]) == {"account_id", "display_name", "role", "active"}
    assert (
        people.get("/internal/project-candidates?account_id=invalid", headers=auth).status_code
        == 400
    )
    with sessions() as s, s.begin():
        s.get(Account, account_id).active = False
    assert people.get("/internal/project-candidates", headers=auth).status_code == 403
