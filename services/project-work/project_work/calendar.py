"""Approved whole-working-day scheduling over explicit immutable calendar data."""

import re
from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from importlib.resources import files
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import tzdata

TZDB_VERSION = tzdata.__version__


@lru_cache(maxsize=256)
def timezone_rules(name):
    if (
        not isinstance(name, str)
        or not re.fullmatch(r"[A-Za-z0-9_+.-]+(?:/[A-Za-z0-9_+.-]+)*", name)
        or any(part in {"", ".", ".."} for part in name.split("/"))
    ):
        raise ValueError("Invalid timezone")
    with files("tzdata.zoneinfo").joinpath(*name.split("/")).open("rb") as stream:
        return ZoneInfo.from_file(stream, key=name)


class CalendarError(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status


def day(value):
    try:
        result = date.fromisoformat(value)
        if result.isoformat() != value or not 1970 <= result.year <= 2199:
            raise ValueError()
        return result
    except (ValueError, TypeError):
        raise CalendarError("invalid_date", 400) from None


def clock(value):
    try:
        result = time.fromisoformat(value)
        if result.strftime("%H:%M") != value or result.tzinfo:
            raise ValueError()
        return result
    except (ValueError, TypeError):
        raise CalendarError("invalid_working_hours", 400) from None


def label(value):
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        raise CalendarError("invalid_label", 400)
    value = " ".join(value.split())
    if not 1 <= len(value) <= 150:
        raise CalendarError("invalid_label", 400)
    return value


def hours(row):
    if type(row.get("working")) is not bool:
        raise CalendarError("invalid_working_status", 400)
    if not row["working"]:
        if row.get("opens") or row.get("closes"):
            raise CalendarError("non_working_hours", 400)
        return {"working": False, "opens": None, "closes": None}
    if clock(row.get("opens")) >= clock(row.get("closes")):
        raise CalendarError("invalid_working_hours", 400)
    return {"working": True, "opens": row["opens"], "closes": row["closes"]}


def normalize(value):
    if not isinstance(value, dict) or set(value) != {"timezone", "week", "holidays", "exceptions"}:
        raise CalendarError("invalid_calendar", 400)
    try:
        timezone = value["timezone"]
        if not isinstance(timezone, str) or len(timezone) > 100:
            raise ValueError()
        timezone_rules(timezone)
    except (ValueError, ZoneInfoNotFoundError, FileNotFoundError, IsADirectoryError, OSError):
        raise CalendarError("invalid_timezone", 400) from None
    week = value["week"]
    if not isinstance(week, list) or len(week) != 7 or any(not isinstance(r, dict) for r in week):
        raise CalendarError("invalid_week", 400)
    if any(type(r.get("weekday")) is not int for r in week) or sorted(
        r["weekday"] for r in week
    ) != list(range(1, 8)):
        raise CalendarError("invalid_week", 400)
    weekly = [
        {"weekday": r["weekday"], **hours(r)} for r in sorted(week, key=lambda r: r["weekday"])
    ]
    if not any(r["working"] for r in weekly):
        raise CalendarError("no_regular_working_day", 400)
    result = {"timezone": timezone, "week": weekly}
    for key in ("holidays", "exceptions"):
        rows = value[key]
        if (
            not isinstance(rows, list)
            or len(rows) > 2000
            or any(not isinstance(r, dict) for r in rows)
        ):
            raise CalendarError("invalid_special_dates", 400)
        normalized, seen = [], set()
        for row in rows:
            current = day(row.get("date")).isoformat()
            if current in seen:
                raise CalendarError("duplicate_special_date", 400)
            seen.add(current)
            normalized.append(
                {
                    "date": current,
                    "label": label(row.get("label")),
                    **(hours(row) if key == "exceptions" else {}),
                }
            )
        result[key] = sorted(normalized, key=lambda r: r["date"])
    return result


def working_hours(config, current):
    iso = current.isoformat()
    exception = next((r for r in config["exceptions"] if r["date"] == iso), None)
    if exception is not None:
        return exception if exception["working"] else None
    if any(r["date"] == iso for r in config["holidays"]):
        return None
    row = config["week"][current.isoweekday() - 1]
    return row if row["working"] else None


def local_boundary(current, value, timezone):
    naive = datetime.combine(current, clock(value))
    zone = timezone_rules(timezone)
    candidates = set()
    for fold in (0, 1):
        local = naive.replace(tzinfo=zone, fold=fold)
        utc = local.astimezone(UTC)
        if utc.astimezone(zone).replace(tzinfo=None) == naive:
            candidates.add(utc)
    if len(candidates) != 1:
        raise CalendarError("ambiguous_or_nonexistent_time")
    return candidates.pop()


def calculate(config, requested_start, duration):
    config = normalize(config)
    current = start = day(requested_start)
    if type(duration) is not int or not 1 <= duration <= 3660:
        raise CalendarError("invalid_duration", 400)
    counted = []
    # A bounded unsupported window fails explicitly; it never produces a guessed date.
    for _ in range(36600):
        if current.year > 2199:
            break
        row = working_hours(config, current)
        if row:
            opening = local_boundary(current, row["opens"], config["timezone"])
            closing = local_boundary(current, row["closes"], config["timezone"])
            if opening >= closing:
                raise CalendarError("invalid_working_hours")
            counted.append(current.isoformat())
            if len(counted) == duration:
                break
        current += timedelta(days=1)
    if len(counted) != duration:
        raise CalendarError("unsupported_schedule_window")
    next_day = current + timedelta(days=1)
    for _ in range(36600):
        if next_day.year > 2199:
            raise CalendarError("unsupported_schedule_window")
        next_hours = working_hours(config, next_day)
        if next_hours:
            handoff = local_boundary(next_day, next_hours["opens"], config["timezone"])
            break
        next_day += timedelta(days=1)
    else:
        raise CalendarError("unsupported_schedule_window")
    first_hours = working_hours(config, day(counted[0]))
    first_open = local_boundary(day(counted[0]), first_hours["opens"], config["timezone"])
    return {
        "requested_start": start.isoformat(),
        "effective_start": counted[0],
        "adjusted": counted[0] != start.isoformat(),
        "duration": duration,
        "counted_dates": counted,
        "timezone": config["timezone"],
        "tzdb_version": TZDB_VERSION,
        "starts_at": first_open.isoformat(),
        "due_at": closing.isoformat(),
        "due_local": closing.astimezone(timezone_rules(config["timezone"])).isoformat(),
        "next_handoff": handoff.isoformat(),
    }
