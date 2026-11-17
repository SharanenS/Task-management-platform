"""Typed calendar boundary; the project-work service owns all calendar data."""

from dataclasses import asdict

import strawberry
from strawberry.types import Info


@strawberry.input
class CalendarWeekdayInput:
    weekday: int
    working: bool
    opens: str | None = None
    closes: str | None = None


@strawberry.input
class CalendarHolidayInput:
    date: str
    label: str


@strawberry.input
class CalendarExceptionInput:
    date: str
    label: str
    working: bool
    opens: str | None = None
    closes: str | None = None


@strawberry.input
class CalendarConfigurationInput:
    timezone: str
    week: list[CalendarWeekdayInput]
    holidays: list[CalendarHolidayInput]
    exceptions: list[CalendarExceptionInput]


@strawberry.type
class CalendarWeekday:
    weekday: int
    working: bool
    opens: str | None
    closes: str | None


@strawberry.type
class CalendarHoliday:
    date: str
    label: str


@strawberry.type
class CalendarException:
    date: str
    label: str
    working: bool
    opens: str | None
    closes: str | None


@strawberry.type
class CalendarConfiguration:
    timezone: str
    week: list[CalendarWeekday]
    holidays: list[CalendarHoliday]
    exceptions: list[CalendarException]


def configuration(value):
    return CalendarConfiguration(
        timezone=value["timezone"],
        week=[CalendarWeekday(**r) for r in value["week"]],
        holidays=[CalendarHoliday(**r) for r in value["holidays"]],
        exceptions=[CalendarException(**r) for r in value["exceptions"]],
    )


@strawberry.type
class CalendarHistory:
    tzdb_version: str
    id: strawberry.ID
    number: int
    actor_id: strawberry.ID
    created_at: str


@strawberry.type
class CompanyCalendarVersion(CalendarHistory):
    config: CalendarConfiguration


def version(value):
    return CompanyCalendarVersion(**{**value, "config": configuration(value["config"])})


@strawberry.type
class CompanyCalendarWorkspace:
    current: CompanyCalendarVersion | None
    history: list[CalendarHistory]


@strawberry.type
class CompanyCalendarPreview:
    tzdb_version: str
    preview_id: strawberry.ID
    base_number: int
    expires_at: str
    config: CalendarConfiguration
    changed_sections: list[str]


@strawberry.input
class PublishCalendarInput:
    preview_id: strawberry.ID
    request_id: strawberry.ID
    confirm: bool


@strawberry.input
class WorkingDaysInput:
    version_id: strawberry.ID
    start: str
    duration: int


@strawberry.type
class WorkingDaysResult:
    tzdb_version: str
    version_id: strawberry.ID
    version_number: int
    requested_start: str
    effective_start: str
    adjusted: bool
    duration: int
    counted_dates: list[str]
    timezone: str
    starts_at: str
    due_at: str
    due_local: str
    next_handoff: str


@strawberry.type
class CalendarQuery:
    @strawberry.field
    async def company_calendar(self, info: Info) -> CompanyCalendarWorkspace:
        value = await info.context.calendar("workspace", {})
        return CompanyCalendarWorkspace(
            current=version(value["current"]) if value["current"] else None,
            history=[CalendarHistory(**r) for r in value["history"]],
        )

    @strawberry.field
    async def calculate_working_days(
        self, info: Info, input: WorkingDaysInput
    ) -> WorkingDaysResult:
        return WorkingDaysResult(**await info.context.calendar("calculate", asdict(input)))


@strawberry.type
class CalendarMutation:
    @strawberry.mutation
    async def preview_company_calendar(
        self, info: Info, input: CalendarConfigurationInput
    ) -> CompanyCalendarPreview:
        value = await info.context.calendar("preview", asdict(input))
        return CompanyCalendarPreview(**{**value, "config": configuration(value["config"])})

    @strawberry.mutation
    async def publish_company_calendar(
        self, info: Info, input: PublishCalendarInput
    ) -> CompanyCalendarVersion:
        return version(await info.context.calendar("publish", asdict(input)))
