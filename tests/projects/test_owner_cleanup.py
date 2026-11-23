from dataclasses import replace
from uuid import uuid4

import pytest
from project_work.delivery_inputs import advance_schedule, open_escalation, record_assessment
from project_work.models import OwnerEscalation

from .fixture import owner_rows
from .test_domain import create
from .test_domain import projects as projects
from .test_domain import setup as setup
from .test_owner_decisions import NOW


def test_owner_cleanup_rejects_foreign_escalation_reference_before_deleting_anything(projects):
    work, sessions, owner, *_ = projects
    run = owner.account_id
    project, _ = create(work, owner, "Owned " + run)
    other, _ = create(work, replace(owner, account_id=str(uuid4())), "Foreign project")
    with sessions() as session, session.begin():
        advance_schedule(session, project["id"], 0)
        assessment = record_assessment(
            session,
            project["id"],
            1,
            project["version"],
            "ASSESSED",
            "2026-11-26T11:30:00Z",
            "Owned S10 " + run,
            now=NOW,
        )
        owned = open_escalation(
            session, project["id"], str(uuid4()), assessment.id, "Owned " + run, "Team " + run
        )
        owned_id = owned.id
        data = owner_rows(session, [project["id"]], {run}, run)
        assert sum(len(rows) for rows in data.values()) == 3
        foreign = OwnerEscalation(
            project_id=other["id"],
            source_request_id=str(uuid4()),
            assessment_id=assessment.id,
            reason="Foreign record",
            affected_team="Foreign team",
        )
        session.add(foreign)
        session.flush()
        with pytest.raises(ValueError, match="ownership mismatch"):
            owner_rows(session, [project["id"]], {run}, run)
        assert session.get(OwnerEscalation, owned_id) is not None
        assert session.get(OwnerEscalation, foreign.id) is not None


def test_empty_owned_scope_does_not_collect_other_projects(projects):
    work, sessions, owner, *_ = projects
    create(work, owner)
    with sessions() as session:
        assert not any(owner_rows(session, [], {str(uuid4())}, str(uuid4())).values())
