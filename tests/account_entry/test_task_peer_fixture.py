import importlib.util
import io
import json
from pathlib import Path
from uuid import uuid4

import pytest
from people.models import Account
from test_access import sessions as sessions

spec = importlib.util.spec_from_file_location(
    "task_peer_fixture", Path(__file__).with_name("fixture.py")
)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def test_exact_owned_peer_creation_inspection_and_cleanup(sessions):
    run, subject = str(uuid4()), str(uuid4())
    with sessions() as s, s.begin():
        created = fixture.task_peer_account(s, run, subject, "task_peer_create")
        assert created["subject"] == subject
        assert fixture.task_peer_account(s, run, subject, "task_peer_inspect")["absent"] is False
        assert fixture.task_peer_account(s, run, subject, "task_peer_cleanup")["cleaned"] is True
        assert fixture.task_peer_account(s, run, subject, "task_peer_cleanup")["cleaned"] is True


@pytest.mark.parametrize("field", ["subject", "profile", "role"])
def test_mismatched_peer_is_preserved(sessions, field):
    run, subject = str(uuid4()), str(uuid4())
    with sessions() as s, s.begin():
        created = fixture.task_peer_account(s, run, subject, "task_peer_create")
        row = s.get(Account, created["accountId"])
        if field == "subject":
            row.subject = str(uuid4())
        if field == "profile":
            row.profile.display_name = "Foreign profile"
        if field == "role":
            row.grants[0].role = "HR"
        s.flush()
        with pytest.raises(ValueError, match="ownership mismatch"):
            fixture.task_peer_account(s, run, subject, "task_peer_cleanup")
        assert s.get(Account, created["accountId"]) is not None


def test_peer_create_never_overwrites_existing_identity(sessions):
    run, subject = str(uuid4()), str(uuid4())
    with sessions() as s, s.begin():
        created = fixture.task_peer_account(s, run, subject, "task_peer_create")
        with pytest.raises(ValueError, match="overwrite"):
            fixture.task_peer_account(s, run, subject, "task_peer_create")
        assert s.get(Account, created["accountId"]).subject == subject


@pytest.mark.parametrize("action", ["task_peer_inspect", "task_peer_cleanup"])
def test_peer_absence_is_verified_after_setup_fails_before_primary_account(
    sessions, monkeypatch, capsys, action
):
    run, subject, peer_subject = str(uuid4()), str(uuid4()), str(uuid4())
    monkeypatch.setenv("PEOPLE_DATABASE_URL", "private-test-database")
    monkeypatch.setattr(fixture, "create_engine", lambda *a, **k: sessions.kw["bind"])
    monkeypatch.setattr(
        fixture.sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "runId": run,
                    "subject": subject,
                    "username": "s1-" + run,
                    "action": action,
                    "value": peer_subject,
                }
            )
        ),
    )
    fixture.main()
    result = json.loads(capsys.readouterr().out)
    assert result["absent"] is True
    assert result["cleaned"] is (action == "task_peer_cleanup")
    with sessions() as session:
        assert session.get(Account, run) is None
