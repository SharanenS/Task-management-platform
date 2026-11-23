from uuid import uuid4

import pytest
from working_calendar.test_api import headers

from .test_coordination import request
from .test_membership_api import MUTATION, change, gql
from .test_membership_api import membership_api as membership_api

CREATE = (
    "mutation($input:CreateCoordinationInput!){createCoordination(input:$input){"
    "id topic version recipients{displayName acknowledgement responseState}}}"
)
QUERY = (
    "query($id:ID!){projectCoordination(id:$id){records{id topic details "
    "recipients{displayName}} hasMore}}"
)


def public(value):
    names = {
        "project_id": "projectId",
        "request_id": "requestId",
        "due_at": "dueAt",
        "acknowledgement_required": "acknowledgementRequired",
    }
    return {names.get(k, k): v for k, v in value.items()}


def test_public_contract_current_authority_and_no_production_response_mutation(membership_api):
    work, gateway, actor, targets, project, employee, _ = membership_api
    assert "errors" not in gql(gateway, MUTATION, input=change(project, employee))
    value = public(request(project, employee))
    created = gql(gateway, CREATE, input=value)
    assert "errors" not in created
    assert created["data"]["createCoordination"]["recipients"][0]["responseState"] == "PENDING"
    assert gql(gateway, CREATE, input=value) == created
    targets[employee]["active"] = False
    rejected = gql(gateway, CREATE, input={**value, "requestId": str(uuid4())})
    assert rejected["errors"][0]["extensions"]["reason"] == "coordination_recipient_ineligible"
    actor["role"], actor["id"] = "EMPLOYEE", employee
    assert gql(gateway, QUERY, id=project["id"])["errors"][0]["extensions"]["code"] == "FORBIDDEN"
    assert (
        work.get("/internal/project-coordination/" + project["id"], headers=headers()).status_code
        == 403
    )
    assert (
        work.post("/internal/project-coordination/respond", headers=headers(), json={}).status_code
        == 404
    )
    actor["role"], actor["id"] = "MANAGER", str(uuid4())
    denied = gql(gateway, QUERY, id=project["id"])
    assert denied["errors"][0]["extensions"]["reason"] == "project_not_found"


@pytest.mark.parametrize(
    "credential", [{}, {"X-Service-Key": "w" * 43}, {"Authorization": "Bearer valid"}]
)
def test_private_coordination_requires_both_credentials(membership_api, credential):
    work, _, _, _, project, *_ = membership_api
    assert (
        work.get("/internal/project-coordination/" + project["id"], headers=credential).status_code
        == 401
    )
    assert (
        work.post(
            "/internal/project-coordination/create",
            headers=credential,
            json=request(project, str(uuid4())),
        ).status_code
        == 401
    )
