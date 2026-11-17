from copy import deepcopy

import pytest
from project_work.calendar import CalendarError, calculate, normalize


def config(timezone="Asia/Colombo"):
    return {
        "timezone": timezone,
        "week": [
            {
                "weekday": i,
                "working": i < 6,
                "opens": "09:00" if i < 6 else None,
                "closes": "17:00" if i < 6 else None,
            }
            for i in range(1, 8)
        ],
        "holidays": [],
        "exceptions": [],
    }


def test_approved_friday_three_day_example_and_next_day_handoff():
    result = calculate(config(), "2026-11-20", 3)
    assert result["counted_dates"] == ["2026-11-20", "2026-11-23", "2026-11-24"]
    assert result["effective_start"] == "2026-11-20" and not result["adjusted"]
    assert result["due_local"] == "2026-11-24T17:00:00+05:30"
    assert result["due_at"] == "2026-11-24T11:30:00+00:00"
    assert result["next_handoff"] == "2026-11-25T03:30:00+00:00"


def test_non_working_start_rolls_forward_and_single_day_counts_start():
    result = calculate(config(), "2026-11-21", 1)
    assert result["effective_start"] == "2026-11-23" and result["adjusted"]
    assert result["counted_dates"] == ["2026-11-23"]


def test_exception_precedence_and_variable_hours_are_calendar_days_not_effort():
    value = config()
    value["holidays"] = [{"date": "2026-11-23", "label": "Holiday"}]
    value["exceptions"] = [
        {
            "date": "2026-11-21",
            "label": "Special day",
            "working": True,
            "opens": "10:00",
            "closes": "12:00",
        },
        {
            "date": "2026-11-23",
            "label": "Reopened holiday",
            "working": True,
            "opens": "10:00",
            "closes": "13:00",
        },
    ]
    result = calculate(value, "2026-11-21", 2)
    assert result["counted_dates"] == ["2026-11-21", "2026-11-23"]
    assert result["due_local"] == "2026-11-23T13:00:00+05:30"
    value["exceptions"][1] = {"date": "2026-11-23", "label": "Closure", "working": False}
    assert calculate(value, "2026-11-21", 2)["counted_dates"] == ["2026-11-21", "2026-11-24"]


def test_leap_year_year_boundary_and_holiday():
    value = config()
    value["holidays"] = [{"date": "2027-01-01", "label": "Fixture holiday"}]
    assert calculate(value, "2026-12-31", 2)["counted_dates"] == ["2026-12-31", "2027-01-04"]
    assert calculate(config(), "2028-02-28", 3)["counted_dates"] == [
        "2028-02-28",
        "2028-02-29",
        "2028-03-01",
    ]


@pytest.mark.parametrize("duration", [0, -1, 1.5, True, "3", None, 3661])
def test_invalid_or_fractional_durations_rejected(duration):
    with pytest.raises(CalendarError) as error:
        calculate(config(), "2026-11-20", duration)
    assert error.value.code == "invalid_duration"


@pytest.mark.parametrize("start", ["2026-02-29", "20261120", "1969-12-31", "2200-01-01", None])
def test_invalid_dates_rejected(start):
    with pytest.raises(CalendarError):
        calculate(config(), start, 1)


def test_timezone_is_explicit_and_configuration_is_not_mutated():
    value = config("America/New_York")
    before = deepcopy(value)
    result = calculate(value, "2026-10-30", 2)
    assert result["starts_at"] == "2026-10-30T13:00:00+00:00"
    assert result["due_at"] == "2026-11-02T22:00:00+00:00"
    assert value == before
    value["timezone"] = ""
    with pytest.raises(CalendarError):
        normalize(value)


@pytest.mark.parametrize("current,hours", [("2026-03-08", "02:30"), ("2026-11-01", "01:30")])
def test_dst_gap_and_ambiguous_times_are_never_guessed(current, hours):
    value = config("America/New_York")
    value["exceptions"] = [
        {
            "date": current,
            "label": "DST fixture",
            "working": True,
            "opens": hours,
            "closes": "17:00",
        }
    ]
    with pytest.raises(CalendarError) as error:
        calculate(value, current, 1)
    assert error.value.code == "ambiguous_or_nonexistent_time"


def test_invalid_calendar_hours_duplicate_dates_and_empty_workweek():
    for update in [
        lambda v: v["week"][0].update(opens="17:00", closes="09:00"),
        lambda v: v["week"][0].update(opens="09:00:00"),
        lambda v: v.update(
            holidays=[{"date": "2026-11-20", "label": "A"}, {"date": "2026-11-20", "label": "B"}]
        ),
        lambda v: v.update(week=[{"weekday": i, "working": False} for i in range(1, 8)]),
    ]:
        value = config()
        update(value)
        with pytest.raises(CalendarError):
            normalize(value)


@pytest.mark.parametrize(
    "timezone",
    ["/etc/passwd", "../UTC", "Etc/../UTC", r"C:\Windows\win.ini", r"Etc\UTC", "localtime"],
)
def test_timezone_keys_cannot_read_host_files_or_host_localtime(timezone):
    value = config(timezone)
    with pytest.raises(CalendarError) as error:
        normalize(value)
    assert error.value.code == "invalid_timezone"
