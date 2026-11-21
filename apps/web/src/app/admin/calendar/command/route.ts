import { NextRequest, NextResponse } from "next/server";
import { authConfig } from "@/shared/auth/config";
import { sameOrigin } from "@/shared/auth/policy";
import { currentSession } from "@/shared/auth/session";
import { adminWorkspace, AccountDenied } from "@/shared/api/account-entry";
import {
  administrationRequest,
  CalendarChangeRejected,
} from "@/shared/api/account-administration";
import {
  PreviewCompanyCalendarDocument,
  PublishCompanyCalendarDocument,
  CalculateWorkingDaysDocument,
} from "@/shared/api/generated";
export async function POST(request: NextRequest) {
  if (!sameOrigin(request.headers.get("origin"), authConfig().origin))
    return NextResponse.json({ error: "Request rejected" }, { status: 403 });
  if (Number(request.headers.get("content-length") ?? 0) > 250000)
    return NextResponse.json(
      { error: "Calendar is too large" },
      { status: 413 },
    );
  try {
    const session = await currentSession();
    if (!session)
      return NextResponse.json(
        { error: "Please sign in again" },
        { status: 401 },
      );
    await adminWorkspace(session);
    const value = await request.json();
    let result;
    if (value.action === "preview")
      result = (
        await administrationRequest(session, PreviewCompanyCalendarDocument, {
          input: value.input,
        })
      ).previewCompanyCalendar;
    else if (value.action === "publish")
      result = (
        await administrationRequest(session, PublishCompanyCalendarDocument, {
          input: value.input,
        })
      ).publishCompanyCalendar;
    else if (value.action === "calculate")
      result = (
        await administrationRequest(session, CalculateWorkingDaysDocument, {
          input: value.input,
        })
      ).calculateWorkingDays;
    else
      return NextResponse.json({ error: "Request rejected" }, { status: 400 });
    return NextResponse.json(
      { result },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch (error) {
    if (error instanceof AccountDenied)
      return NextResponse.json({ error: "Access denied" }, { status: 403 });
    if (error instanceof CalendarChangeRejected) {
      const messages: Record<string, string> = {
        invalid_timezone:
          "Your device’s local time could not be used. Check its date and time settings, then reload the calendar.",
        invalid_week: "Configure each of the seven weekdays once.",
        invalid_working_hours:
          "Opening time must be before closing time on the same day.",
        no_regular_working_day: "Select at least one regular working weekday.",
        invalid_date: "Use valid dates between 1970 and 2199.",
        duplicate_special_date:
          "Each holiday or exception date must appear only once in its list.",
        invalid_duration:
          "Duration must be a whole number from 1 to 3660 working days.",
        ambiguous_or_nonexistent_time:
          "A selected local time is ambiguous or missing because of a timezone transition. Configure an explicit date exception with valid hours.",
        unsupported_timezone_version:
          "The matching historical timezone rules are unavailable. Restore those rules before recalculating this version.",
        preview_expired:
          "The preview expired. Preview the calendar again before publishing.",
        stale_calendar_preview:
          "Another calendar version was published. Refresh and preview your changes against the current version.",
        preview_already_published:
          "This preview has already been published. Refresh the calendar history.",
        no_calendar_changes:
          "These values match the current calendar. There are no changes to publish.",
        unsupported_schedule_window:
          "This schedule exceeds the supported calendar window. Check its start and duration.",
        confirmation_required:
          "Confirm the reviewed calendar before publishing.",
      };
      return NextResponse.json(
        {
          error:
            messages[error.reason] ??
            "The calendar request was rejected. Check its values and preview the current version again.",
        },
        { status: 409 },
      );
    }
    return NextResponse.json(
      {
        error:
          "Calendar services are unavailable. Refresh to check the recorded outcome before trying again.",
      },
      { status: 503 },
    );
  }
}
