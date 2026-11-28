from dataclasses import replace
from uuid import uuid4

import pytest
from project_work.models import SchedulePreview, TaskDependency, WorkTask
from sqlalchemy import select

from .fixture import schedule_rows
from .test_domain import create
from .test_domain import projects as projects
from .test_domain import setup as setup
from .test_scheduling import plan, prepared
from .test_tasks import directory


def test_schedule_cleanup_rejects_nonowned_preview_actor(projects):
    service, sessions, owner, leader, employee, peer, project, receipts = prepared(projects)
    preview = service.preview(lambda: leader, directory, plan(project, receipts[0]))
    actors = {leader.account_id, employee.account_id}
    with sessions() as session, session.begin():
        assert len(schedule_rows(session, [project["id"]], actors)[SchedulePreview]) == 1
        session.get(SchedulePreview, preview["preview_id"]).actor_id = str(uuid4())
        session.flush()
        with pytest.raises(ValueError, match="ownership mismatch"):
            schedule_rows(session, [project["id"]], actors)


def test_schedule_cleanup_rejects_dependency_outside_owned_tasks(projects):
    service, sessions, owner, leader, employee, peer, project, receipts = prepared(projects)
    foreign_owner = replace(owner, account_id=str(uuid4()))
    foreign_project, _ = create(projects[0], foreign_owner, name="Foreign project")
    with sessions() as session, session.begin():
        foreign_task = WorkTask(
            project_id=foreign_project["id"],
            creator_id=foreign_owner.account_id,
            title="Foreign task",
            instructions="Retained",
            acceptance_criteria="Retained",
        )
        session.add(foreign_task)
        session.flush()
        session.add(TaskDependency(task_id=receipts[0]["task_id"], prerequisite_id=foreign_task.id))
        session.flush()
        with pytest.raises(ValueError, match="dependency ownership mismatch"):
            schedule_rows(session, [project["id"]], {leader.account_id, employee.account_id})
        assert session.scalar(select(TaskDependency)) is not None
        assert session.get(WorkTask, foreign_task.id) is not None
