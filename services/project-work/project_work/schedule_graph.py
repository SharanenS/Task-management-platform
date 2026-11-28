"""Bounded working-day dependency analysis; no implicit resource-capacity scheduling."""

from datetime import UTC, datetime

from .calendar import CalendarError, calculate, day, timezone_rules
from .projects import ProjectError

MAX_TASKS = 250


def analyze(config, nodes, now=None):
    if len(nodes) > MAX_TASKS:
        raise ProjectError("schedule_limit", 400)
    by_id = {n["id"]: n for n in nodes}
    if len(by_id) != len(nodes):
        raise ProjectError("invalid_schedule", 400)
    pending, dependents = {}, {key: [] for key in by_id}
    for node in nodes:
        dependencies = node.get("prerequisites", [])
        if len(set(dependencies)) != len(dependencies) or len(dependencies) > MAX_TASKS:
            raise ProjectError("invalid_dependencies", 400)
        if any(key not in by_id or key == node["id"] for key in dependencies):
            raise ProjectError("invalid_dependencies", 400)
        pending[node["id"]] = len(dependencies)
        for key in dependencies:
            dependents[key].append(node["id"])
    ready = sorted(key for key, count in pending.items() if count == 0)
    order = []
    while ready:
        key = ready.pop()
        order.append(key)
        for dependent in dependents[key]:
            pending[dependent] -= 1
            if pending[dependent] == 0:
                ready.append(dependent)
    if len(order) != len(nodes):
        raise ProjectError("dependency_cycle")
    clock = now or datetime.now(UTC)
    if clock.utcoffset() is None:
        raise ProjectError("invalid_schedule", 400)
    rows = {}
    for key in order:
        node = by_id[key]
        dependencies = node.get("prerequisites", [])
        row = {
            "id": key,
            "requested_start": node.get("requested_start"),
            "duration": node.get("duration"),
            "prerequisites": dependencies,
            "effective_start": None,
            "starts_at": None,
            "due_at": None,
            "next_handoff": None,
            "adjusted": False,
            "readiness": "UNASSESSED",
            "issue": None,
        }
        rows[key] = row
        if node.get("status") == "CANCELLED":
            row["issue"] = "CANCELLED"
            continue
        if not node.get("eligible", False):
            row["issue"] = "ASSIGNEE_INELIGIBLE"
            continue
        if not node.get("requested_start") or node.get("duration") is None:
            row["issue"] = "MISSING_PLAN"
            continue
        if any(rows[dep]["due_at"] is None for dep in dependencies):
            row["issue"] = "PREREQUISITE_UNASSESSED"
            continue
        start = day(node["requested_start"]).isoformat()
        for dep in dependencies:
            local = (
                datetime.fromisoformat(rows[dep]["next_handoff"])
                .astimezone(timezone_rules(config["timezone"]))
                .date()
                .isoformat()
            )
            start = max(start, local)
        try:
            result = calculate(config, start, node["duration"])
        except CalendarError as error:
            raise ProjectError(error.code, error.status) from None
        for field in ("effective_start", "starts_at", "due_at", "next_handoff"):
            row[field] = result[field]
        row["adjusted"] = row["effective_start"] != node["requested_start"]
        if any(by_id[dep]["status"] != "COMPLETED" for dep in dependencies):
            row["readiness"] = "WAITING_FOR_PREREQUISITES"
        elif clock < datetime.fromisoformat(row["starts_at"]):
            row["readiness"] = "WAITING_FOR_DATE"
        else:
            row["readiness"] = "READY"
        if node["status"] != "COMPLETED" and clock > datetime.fromisoformat(row["due_at"]):
            row["issue"] = "INCOMPLETE_PAST_FINISH"
    active = [row for row in rows.values() if by_id[row["id"]]["status"] != "CANCELLED"]
    # A calculable path does not make unknown or overdue work a reliable forecast.
    assessed = bool(active) and all(row["issue"] is None for row in active)
    forecast = max((row["due_at"] for row in active), default=None) if assessed else None
    overlaps = []
    scheduled = sorted((r for r in active if r["starts_at"] and r["due_at"]), key=lambda r: r["id"])
    for index, left in enumerate(scheduled):
        for right in scheduled[index + 1 :]:
            if by_id[left["id"]].get("assignee_id") == by_id[right["id"]].get(
                "assignee_id"
            ) and max(left["starts_at"], right["starts_at"]) <= min(
                left["due_at"], right["due_at"]
            ):
                if len(overlaps) >= 100:
                    continue
                overlaps.append({"task_id": left["id"], "other_task_id": right["id"]})
    return {
        "state": "ASSESSED" if assessed else "UNASSESSED",
        "forecast_at": forecast,
        "tasks": [rows[n["id"]] for n in nodes],
        "overlaps": overlaps,
        "capacity_checked": False,
    }
