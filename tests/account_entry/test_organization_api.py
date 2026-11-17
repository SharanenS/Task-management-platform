from uuid import uuid4

import pytest
from people.models import Account
from sqlalchemy import select
from test_api import SETTINGS
from test_api import boundary as boundary


@pytest.mark.parametrize("role", ["EMPLOYEE", "MANAGER", "HR", "ADMIN"])
def test_organization_gateway_and_private_authority(boundary, role):
    people, gateway, sessions, identity = boundary
    with sessions() as s:
        account = s.scalar(select(Account).where(Account.subject == identity.subject))
        account.grants[0].role = role
        s.commit()
    query = {"query": "{ organizationWorkspace { departments { id } employees { id } } }"}
    mutation = {
        "query": (
            "mutation($input: OrganizationChangeInput!) { "
            "changeOrganization(input:$input) { state } }"
        ),
        "variables": {
            "input": {
                "requestId": str(uuid4()),
                "action": "EMPLOYEE_CREATE",
                "name": "Directory person",
            }
        },
    }
    headers = {"Authorization": "Bearer valid-provider-token", "X-Actor-Role": "ADMIN"}
    for request in (query, mutation):
        result = gateway.post("/graphql", json=request, headers=headers)
        assert result.status_code == 200
        if role == "ADMIN":
            assert "errors" not in result.json()
        else:
            assert result.json()["errors"][0]["extensions"]["code"] == "FORBIDDEN"
    for headers in (
        {},
        {"X-Service-Key": SETTINGS.service_key},
        {"Authorization": "Bearer valid-provider-token"},
        {"X-Service-Key": SETTINGS.service_key, "Authorization": "Bearer forged"},
    ):
        assert people.get("/internal/admin/organization", headers=headers).status_code == 401
        assert (
            people.post("/internal/admin/organization", json={}, headers=headers).status_code == 401
        )
    result = people.get(
        "/internal/admin/organization",
        headers={
            "X-Service-Key": SETTINGS.service_key,
            "Authorization": "Bearer valid-provider-token",
        },
    )
    assert result.status_code == (200 if role == "ADMIN" else 403)
