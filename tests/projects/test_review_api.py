from uuid import uuid4

import pytest
from working_calendar.test_api import headers

from .test_membership_api import gql
from .test_membership_api import membership_api as membership_api
from .test_schedule_api import COMMIT, PREVIEW
from .test_task_api import MUTATION, prepared

QUERY = (
    "query($id:ID!){projectReviews(id:$id,page:0){isLeader canReview fallbackId "
    "tasks{id version own status instructions progress submissions{id version summary pending "
    "decision{selfApproval outcome feedback}}}}}"
)
EXECUTE = (
    "mutation($input:ExecuteTaskInput!){executeTask(input:$input){taskId version projectVersion}}"
)
DECIDE = (
    "mutation($input:ReviewCompletionInput!){reviewCompletion(input:$input)"
    "{taskId version projectVersion}}"
)


def test_graphql_execution_submission_self_confirmation_and_peer_privacy(membership_api):
    work, gateway, actor, targets, project, leader, peer = membership_api
    task = gql(gateway, MUTATION, input=prepared(membership_api))["data"]["changeTask"]
    p = gql(
        gateway,
        PREVIEW,
        input={
            "projectId": project["id"],
            "taskId": task["taskId"],
            "projectVersion": task["projectVersion"],
            "version": task["version"],
            "requestedStart": "2026-01-05",
            "duration": 1,
            "prerequisites": [],
            "reason": "Review fixture",
        },
    )["data"]["previewTaskSchedule"]
    saved = gql(
        gateway,
        COMMIT,
        input={
            "projectId": project["id"],
            "previewId": p["previewId"],
            "requestId": str(uuid4()),
            "confirm": True,
        },
    )["data"]["commitTaskSchedule"]
    current = gql(gateway, QUERY, id=project["id"])["data"]["projectReviews"]
    version = current["tasks"][0]["version"]
    value = {
        "projectId": project["id"],
        "taskId": task["taskId"],
        "projectVersion": saved["projectVersion"],
        "version": version,
        "requestId": str(uuid4()),
        "action": "START",
        "note": "My work begins",
        "progress": 0,
        "blocker": None,
        "confirm": True,
    }
    started = gql(gateway, EXECUTE, input=value)
    assert "errors" not in started
    value = {
        **value,
        "requestId": str(uuid4()),
        "action": "SUBMIT",
        "version": started["data"]["executeTask"]["version"],
        "projectVersion": started["data"]["executeTask"]["projectVersion"],
    }
    submitted = gql(gateway, EXECUTE, input=value)["data"]["executeTask"]
    row = gql(gateway, QUERY, id=project["id"])["data"]["projectReviews"]["tasks"][0]
    assert row["status"] == "AWAITING_REVIEW" and row["submissions"][0]["pending"]
    decision = {
        "projectId": project["id"],
        "taskId": task["taskId"],
        "submissionId": row["submissions"][0]["id"],
        "projectVersion": submitted["projectVersion"],
        "version": submitted["version"],
        "requestId": str(uuid4()),
        "outcome": "APPROVE",
        "feedback": "Accepted against criteria",
        "selfConfirm": False,
        "confirm": True,
    }
    rejected = gql(gateway, DECIDE, input=decision)
    assert rejected["errors"][0]["extensions"]["reason"] == "explicit_self_approval_required"
    accepted = gql(gateway, DECIDE, input={**decision, "selfConfirm": True})
    assert "errors" not in accepted
    assert gql(gateway, QUERY, id=project["id"])["data"]["projectReviews"]["tasks"][0][
        "submissions"
    ][0]["decision"]["selfApproval"]
    actor["id"] = peer
    assert gql(gateway, QUERY, id=project["id"])["data"]["projectReviews"]["tasks"] == []
    assert gql(gateway, DECIDE, input=decision)["errors"][0]["extensions"]["code"] == "FORBIDDEN"
    actor["active"] = False
    assert (
        work.get("/internal/project-reviews/" + project["id"], headers=headers()).status_code == 403
    )


@pytest.mark.parametrize(
    "credential", [{}, {"X-Service-Key": "w" * 43}, {"Authorization": "Bearer valid"}]
)
def test_review_private_boundary_requires_both_verified_credentials(membership_api, credential):
    work, _, _, _, project, *_ = membership_api
    assert (
        work.get("/internal/project-reviews/" + project["id"], headers=credential).status_code
        == 401
    )
    for operation in ("execute", "decide"):
        assert (
            work.post(
                "/internal/project-reviews/" + operation, headers=credential, json={}
            ).status_code
            == 401
        )


def test_malformed_review_project_identifier_is_not_reported_as_service_outage(membership_api):
    _, gateway, *_ = membership_api
    response = gql(gateway, QUERY, id="not-a-project-identifier")
    assert response["errors"][0]["extensions"] == {
        "code": "PROJECT_REJECTED",
        "reason": "project_not_found",
    }
