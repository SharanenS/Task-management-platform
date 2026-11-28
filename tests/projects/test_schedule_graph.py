from datetime import UTC, datetime

import pytest
from project_work.projects import ProjectError
from project_work.schedule_graph import analyze
from working_calendar.test_calendar import config

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def node(key, start="2026-01-02", duration=1, dependencies=None, **fields):
    return {
        "id": key,
        "requested_start": start,
        "duration": duration,
        "prerequisites": dependencies or [],
        "status": "PENDING",
        "eligible": True,
        "assignee_id": "employee",
        **fields,
    }


def test_independent_paths_overlap_without_serialization():
    result = analyze(config(), [node("a", duration=3), node("b", duration=1)], NOW)
    assert result["state"] == "ASSESSED"
    assert result["tasks"][0]["effective_start"] == result["tasks"][1]["effective_start"]
    assert result["tasks"][0]["due_at"].startswith("2026-01-06")
    assert result["overlaps"] == [{"task_id": "a", "other_task_id": "b"}]
    assert result["capacity_checked"] is False


def test_dependency_handoff_waits_next_working_day_and_completion():
    rows = [node("a"), node("b", dependencies=["a"])]
    result = analyze(config(), rows, NOW)
    assert result["tasks"][1]["effective_start"] == "2026-01-05"
    assert result["tasks"][1]["readiness"] == "WAITING_FOR_PREREQUISITES"
    assert result["tasks"][1]["adjusted"] is True
    rows[0]["status"] = "AWAITING_REVIEW"
    assert analyze(config(), rows, NOW)["tasks"][1]["readiness"] == "WAITING_FOR_PREREQUISITES"
    rows[0]["status"] = "COMPLETED"
    assert analyze(config(), rows, NOW)["tasks"][1]["readiness"] == "WAITING_FOR_DATE"
    rows[1]["status"] = "IN_PROGRESS"
    later = datetime(2026, 1, 5, 12, tzinfo=UTC)
    assert analyze(config(), rows, later)["tasks"][1]["readiness"] == "READY"


@pytest.mark.parametrize(
    "rows,code",
    [
        ([node("a", dependencies=["a"])], "invalid_dependencies"),
        ([node("a", dependencies=["foreign"])], "invalid_dependencies"),
        ([node("a", dependencies=["b"]), node("b", dependencies=["a"])], "dependency_cycle"),
        ([node("a", dependencies=["b", "b"]), node("b")], "invalid_dependencies"),
    ],
)
def test_invalid_or_cyclic_edges_fail(rows, code):
    with pytest.raises(ProjectError) as error:
        analyze(config(), rows, NOW)
    assert error.value.code == code


@pytest.mark.parametrize(
    "fields,issue",
    [
        ({"requested_start": None}, "MISSING_PLAN"),
        ({"eligible": False}, "ASSIGNEE_INELIGIBLE"),
    ],
)
def test_unknown_inputs_propagate_without_inventing_forecast(fields, issue):
    result = analyze(config(), [node("a", **fields), node("b", dependencies=["a"])], NOW)
    assert result["state"] == "UNASSESSED" and result["forecast_at"] is None
    assert result["tasks"][0]["issue"] == issue
    assert result["tasks"][1]["due_at"] is None


def test_overdue_incomplete_does_not_move_commitment_or_invent_forecast():
    result = analyze(config(), [node("a")], datetime(2026, 1, 3, tzinfo=UTC))
    assert result["forecast_at"] is None
    assert result["tasks"][0]["due_at"].startswith("2026-01-02")
    assert result["tasks"][0]["issue"] == "INCOMPLETE_PAST_FINISH"


def test_nonworking_requested_start_rolls_forward_and_join_uses_longest_path():
    result = analyze(
        config(),
        [node("a", start="2026-01-03"), node("b", duration=4), node("c", dependencies=["a", "b"])],
        NOW,
    )
    assert result["tasks"][0]["effective_start"] == "2026-01-05"
    assert result["tasks"][2]["effective_start"] == "2026-01-08"


def test_empty_network_is_unassessed():
    assert analyze(config(), [], NOW)["forecast_at"] is None


def test_workload_warning_projection_is_bounded_without_serializing_tasks():
    result = analyze(config(), [node(str(i)) for i in range(20)], NOW)
    assert len(result["overlaps"]) == 100
    assert len({task["starts_at"] for task in result["tasks"]}) == 1
    assert result["state"] == "ASSESSED" and result["capacity_checked"] is False
