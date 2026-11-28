from uuid import uuid4

import pytest
from project_work.models import TaskReviewDecision, TaskSubmission, WorkTask
from sqlalchemy import select

from .fixture import review_rows
from .test_domain import projects as projects
from .test_domain import setup as setup
from .test_reviews import act, decision, prepared


@pytest.mark.parametrize("boundary", ["submission", "decision"])
def test_cleanup_refuses_foreign_review_actor_without_deleting_history(projects, boundary):
    service, sessions, owner, leader, target, peer, project, task = prepared(projects)
    act(service, target, project, task)
    act(service, target, project, task, "SUBMIT")
    if boundary == "decision":
        service.decide(
            lambda: leader,
            lambda ids: [
                {"account_id": v, "display_name": "Member", "active": True, "role": "EMPLOYEE"}
                for v in ids
            ],
            decision(service, leader, project, task),
        )
    actors = {r.account_id for r in (owner, leader, target, peer)}
    with sessions() as session, session.begin():
        owned = review_rows(session, [project["id"]], actors)
        assert sum(len(v) for v in owned.values()) == (3 if boundary == "decision" else 2)
        if boundary == "submission":
            row = session.scalar(select(TaskSubmission))
            row.submitter_id = str(uuid4())
        else:
            row = session.scalar(select(TaskReviewDecision))
            row.actor_id = str(uuid4())
        session.flush()
        with pytest.raises(ValueError, match="ownership mismatch"):
            review_rows(session, [project["id"]], actors)
        assert session.get(WorkTask, task["task_id"]) is not None
