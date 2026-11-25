from uuid import uuid4

import pytest
from people.access import AccessDenied, resolve_actor
from people.models import Account
from people.project_directory import ProjectDirectory
from sqlalchemy import select
from test_access import provision
from test_access import sessions as sessions
from test_api import boundary as boundary


def test_employee_private_exact_reference_is_minimal_and_live(sessions):
    with sessions() as s:
        caller = provision(s)
        employee = provision(s)
        manager = provision(s, role="MANAGER")
        inactive = provision(s, active=False)
        employee_id = resolve_actor(s, employee).account_id
        manager_id = resolve_actor(s, manager).account_id
        inactive_id = s.scalar(select(Account.id).where(Account.subject == inactive.subject))
    values = ProjectDirectory(sessions).task_references(
        caller, [employee_id, manager_id, inactive_id, str(uuid4())]
    )
    assert values == [
        {
            "account_id": employee_id,
            "display_name": "Test Account",
            "active": True,
            "role": "EMPLOYEE",
        }
    ]


@pytest.mark.parametrize("ids", [None, "all", ["not-a-uuid"], [str(uuid4())] * 26])
def test_reference_batch_is_bounded(sessions, ids):
    with sessions() as s:
        caller = provision(s)
    with pytest.raises((ValueError, TypeError, AttributeError)):
        ProjectDirectory(sessions).task_references(caller, ids)


def test_hr_cannot_read_reference_batch(sessions):
    with sessions() as s:
        caller = provision(s, role="HR")
    with pytest.raises(AccessDenied):
        ProjectDirectory(sessions).task_references(caller, [])


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-Service-Key": "s" * 43},
        {"Authorization": "Bearer valid-provider-token"},
        {"X-Service-Key": "s" * 43, "Authorization": "Bearer forged"},
    ],
)
def test_private_reference_endpoint_requires_both_credentials(boundary, headers):
    people, *_ = boundary
    assert (
        people.post(
            "/internal/task-references", headers=headers, json={"account_ids": []}
        ).status_code
        == 401
    )
