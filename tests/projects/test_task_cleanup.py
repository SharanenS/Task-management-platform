from dataclasses import replace
from uuid import uuid4

import pytest
from project_work.models import TaskAssignment, WorkTask
from sqlalchemy import select

from .fixture import task_rows
from .test_domain import create
from .test_domain import projects as projects
from .test_domain import setup as setup
from .test_tasks import change, directory, prepare


def test_task_cleanup_rejects_foreign_assignee_and_collects_no_foreign_project(projects):
    tasks, sessions, owner, leader, employee, peer, project = prepare(projects)
    result = tasks.change(lambda: leader, directory, change(project, employee))
    actors = {leader.account_id, employee.account_id}
    with sessions() as s, s.begin():
        assert sum(len(v) for v in task_rows(s, [project["id"]], actors).values()) == 3
        row = s.scalar(select(TaskAssignment).where(TaskAssignment.task_id == result["task_id"]))
        row.account_id = str(uuid4())
        s.flush()
        with pytest.raises(ValueError, match="ownership mismatch"):
            task_rows(s, [project["id"]], actors)
        assert s.get(WorkTask, result["task_id"]) is not None


def test_task_cleanup_rejects_foreign_project_owned_actor_reference(projects):
    tasks, sessions, owner, leader, employee, peer, project = prepare(projects)
    foreign, _ = create(projects[0], replace(owner, account_id=str(uuid4())))
    with sessions() as s, s.begin():
        row = WorkTask(
            project_id=foreign["id"],
            creator_id=leader.account_id,
            title="Foreign",
            instructions="Private",
            acceptance_criteria="Private",
        )
        s.add(row)
        s.flush()
        with pytest.raises(ValueError, match="ownership mismatch"):
            task_rows(s, [project["id"]], {leader.account_id})
        assert s.get(WorkTask, row.id) is not None
