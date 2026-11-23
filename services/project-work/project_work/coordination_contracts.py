"""Validated coordination responses for the later employee response journey.

S9 deliberately exposes no production response-writing endpoint.
"""

from datetime import datetime

from .projects import ProjectError


def content(value, maximum=2000):
    if not isinstance(value, str):
        raise ProjectError("invalid_coordination", 400)
    value = value.strip()
    if not value or len(value) > maximum or any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ProjectError("invalid_coordination", 400)
    return value


def instant(value):
    try:
        result = datetime.fromisoformat(value)
        if result.utcoffset() is None:
            raise ValueError()
        return result
    except (ValueError, TypeError):
        raise ProjectError("invalid_coordination_time", 400) from None


def response_contract(kind, value):
    """Return a strict structured payload; identity must come from server authority."""
    if not isinstance(value, dict):
        raise ProjectError("invalid_coordination_response", 400)
    if kind == "UPDATE" and set(value) == {"progress", "blockers", "next_steps"}:
        return {k: content(v) for k, v in value.items()}
    if kind in {"MEETING", "CHECK_IN"}:
        if value == {"decision": "ACCEPT"}:
            return value.copy()
        if (
            set(value) == {"decision", "alternative_time", "reason"}
            and value["decision"] == "ALTERNATIVE"
        ):
            instant(value["alternative_time"])
            return {**value, "reason": content(value["reason"])}
    raise ProjectError("invalid_coordination_response", 400)
