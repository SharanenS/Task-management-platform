from uuid import uuid4

import pytest
from working_calendar.test_api import headers

from .test_membership_api import gql
from .test_membership_api import membership_api as membership_api
from .test_task_api import MUTATION, prepared

QUERY = (
    "query($id:ID!){projectSchedule(id:$id){canPlan state forecastAt currentDeadline "
    "tasks{title plan{id requestedStart duration dueAt readiness} original{dueAt}} "
    "history{id} overlaps{taskId}}}"
)
PREVIEW = (
    "mutation($input:PreviewTaskScheduleInput!){previewTaskSchedule(input:$input)"
    "{previewId after{state forecastAt} exceedsDeadline}}"
)
COMMIT = (
    "mutation($input:CommitTaskScheduleInput!){commitTaskSchedule(input:$input)"
    "{projectVersion scheduleVersion}}"
)


def test_graphql_schedule_private_projection_and_confirmed_save(membership_api):
    work, gateway, actor, targets, project, leader, peer = membership_api
    value = prepared(membership_api)
    receipt = gql(gateway, MUTATION, input=value)["data"]["changeTask"]
    planned = {
        "projectId": project["id"],
        "taskId": receipt["taskId"],
        "projectVersion": receipt["projectVersion"],
        "version": receipt["version"],
        "requestedStart": "2030-01-02",
        "duration": 3,
        "prerequisites": [],
        "reason": "Owned schedule",
    }
    response = gql(gateway, PREVIEW, input=planned)
    assert "errors" not in response
    preview = response["data"]["previewTaskSchedule"]
    assert preview["after"]["state"] == "ASSESSED" and preview["exceedsDeadline"] is True
    commit = {
        "projectId": project["id"],
        "previewId": preview["previewId"],
        "requestId": str(uuid4()),
        "confirm": True,
    }
    assert "errors" not in gql(gateway, COMMIT, input=commit)
    own = gql(gateway, QUERY, id=project["id"])["data"]["projectSchedule"]
    assert own["tasks"][0]["plan"]["requestedStart"] == "2030-01-02"
    actor["id"] = peer
    peer_view = gql(gateway, QUERY, id=project["id"])["data"]["projectSchedule"]
    assert peer_view["tasks"] == [] and peer_view["state"] is None
    assert peer_view["history"] == [] and peer_view["overlaps"] == []
    assert gql(gateway, PREVIEW, input=planned)["errors"][0]["extensions"]["code"] == "FORBIDDEN"


@pytest.mark.parametrize(
    "credential", [{}, {"X-Service-Key": "w" * 43}, {"Authorization": "Bearer valid"}]
)
def test_schedule_private_boundary_requires_two_credentials(membership_api, credential):
    work, _, _, _, project, *_ = membership_api
    assert (
        work.get("/internal/project-schedule/" + project["id"], headers=credential).status_code
        == 401
    )
    assert (
        work.post("/internal/project-schedule/preview", headers=credential, json={}).status_code
        == 401
    )


def test_current_role_and_activity_cannot_be_forged_for_schedule(membership_api):
    work, gateway, actor, targets, project, leader, peer = membership_api
    prepared(membership_api)
    actor["active"] = False
    response = work.get("/internal/project-schedule/" + project["id"], headers=headers())
    assert response.status_code == 403
