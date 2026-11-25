from uuid import uuid4

import pytest
from working_calendar.test_api import headers

from .test_membership_api import change, gql
from .test_membership_api import membership_api as membership_api

QUERY = (
    "query($id:ID!){projectTasks(id:$id){canPlan project{id version} "
    "tasks{id title status assigneeName details{instructions acceptanceCriteria "
    "assigneeId history{before after}}}}}"
)
MUTATION = (
    "mutation($input:ChangeTaskInput!){changeTask(input:$input){taskId version projectVersion}}"
)


def prepared(fixture):
    work, gateway, actor, targets, project, leader, peer = fixture
    for target, responsibility in ((leader, "LEADER"), (peer, "CONTRIBUTOR")):
        value = change(project, target, responsibility=responsibility)
        result = gql(
            gateway,
            "mutation($input:ChangeProjectMembershipInput!){changeProjectMembership(input:$input){version}}",
            input=value,
        )
        assert "errors" not in result
        project["version"] = result["data"]["changeProjectMembership"]["version"]
    actor["id"], actor["role"] = leader, "EMPLOYEE"
    return {
        "projectId": project["id"],
        "projectVersion": project["version"],
        "taskId": None,
        "requestId": str(uuid4()),
        "version": 0,
        "action": "CREATE",
        "title": "Task title",
        "instructions": "Private description",
        "acceptanceCriteria": "Private acceptance",
        "assigneeId": leader,
        "reason": "Planned by current leader",
        "confirm": True,
    }


def test_gateway_private_task_projection_and_ignored_forged_headers(membership_api):
    work, gateway, actor, targets, project, leader, peer = membership_api
    value = prepared(membership_api)
    result = gql(gateway, MUTATION, input=value)
    assert "errors" not in result
    assert gql(gateway, MUTATION, input=value) == result
    owner_view = gql(gateway, QUERY, id=project["id"])["data"]["projectTasks"]
    assert owner_view["canPlan"] is True
    assert owner_view["tasks"][0]["details"]["instructions"] == "Private description"
    actor["id"] = peer
    response = gql(gateway, QUERY, id=project["id"])["data"]["projectTasks"]
    assert response["canPlan"] is False
    assert response["tasks"][0]["details"] is None
    denied = gql(gateway, MUTATION, input={**value, "requestId": str(uuid4())})
    assert denied["errors"][0]["extensions"]["code"] == "FORBIDDEN"
    actor["active"] = False
    response = gateway.post(
        "/graphql",
        headers={"Authorization": "Bearer valid"},
        json={"query": QUERY, "variables": {"id": project["id"]}},
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Access denied"}


def test_gateway_rechecks_target_role_and_does_not_add_a_second_task(membership_api):
    work, gateway, actor, targets, project, leader, peer = membership_api
    value = prepared(membership_api)
    targets[peer]["role"] = "MANAGER"
    response = gql(gateway, MUTATION, input={**value, "assigneeId": peer})
    assert response["errors"][0]["extensions"]["reason"] == "task_assignee_ineligible"
    assert gql(gateway, QUERY, id=project["id"])["data"]["projectTasks"]["tasks"] == []
    candidates = gql(
        gateway,
        "query($id:ID!){taskCandidates(id:$id){candidates{accountId displayName}}}",
        id=project["id"],
    )
    assert [r["accountId"] for r in candidates["data"]["taskCandidates"]["candidates"]] == [leader]


@pytest.mark.parametrize(
    "credential", [{}, {"X-Service-Key": "w" * 43}, {"Authorization": "Bearer valid"}]
)
def test_private_task_boundary_requires_both_credentials(membership_api, credential):
    work, _, _, _, project, *_ = membership_api
    assert (
        work.get("/internal/project-tasks/" + project["id"], headers=credential).status_code == 401
    )


def test_valid_identity_cannot_bypass_contextual_planning_directly(membership_api):
    work, _, _, _, project, *_ = membership_api
    assert (
        work.post("/internal/project-tasks/change", headers=headers(), json={}).status_code == 400
    )
    assert work.get("/internal/project-tasks/" + str(uuid4()), headers=headers()).status_code == 404
