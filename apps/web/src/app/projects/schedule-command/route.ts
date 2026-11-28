import { NextRequest, NextResponse } from "next/server";
import { sameOrigin } from "@/shared/auth/policy";
import { authConfig } from "@/shared/auth/config";
import { currentSession } from "@/shared/auth/session";
import { accountEntry, AccountDenied } from "@/shared/api/account-entry";
import {
  administrationRequest,
  ProjectChangeRejected,
} from "@/shared/api/account-administration";
import {
  PreviewTaskScheduleDocument,
  CommitTaskScheduleDocument,
} from "@/shared/api/generated";

export async function POST(request: NextRequest) {
  if (!sameOrigin(request.headers.get("origin"), authConfig().origin))
    return NextResponse.json({ error: "Request rejected" }, { status: 403 });
  if (Number(request.headers.get("content-length") ?? 0) > 40000)
    return NextResponse.json(
      { error: "Request is too large" },
      { status: 413 },
    );
  try {
    const session = await currentSession();
    if (!session)
      return NextResponse.json(
        { error: "Please sign in again" },
        { status: 401 },
      );
    const actor = await accountEntry(session);
    if (actor.companyRoles[0] !== "EMPLOYEE") throw new AccountDenied();
    const value = await request.json();
    if (value.action === "preview") {
      const result = await administrationRequest(
        session,
        PreviewTaskScheduleDocument,
        { input: value.input },
      );
      return NextResponse.json(result.previewTaskSchedule, {
        headers: { "Cache-Control": "no-store" },
      });
    }
    if (value.action === "commit") {
      const result = await administrationRequest(
        session,
        CommitTaskScheduleDocument,
        { input: value.input },
      );
      return NextResponse.json(result.commitTaskSchedule, {
        headers: { "Cache-Control": "no-store" },
      });
    }
    return NextResponse.json({ error: "Invalid action" }, { status: 400 });
  } catch (error) {
    if (error instanceof AccountDenied)
      return NextResponse.json({ error: "Access denied" }, { status: 403 });
    if (error instanceof SyntaxError)
      return NextResponse.json({ error: "Invalid request" }, { status: 400 });
    if (error instanceof ProjectChangeRejected) {
      const messages: Record<string, string> = {
        dependency_cycle:
          "These prerequisites create a cycle. Choose a one-way dependency path.",
        invalid_dependencies:
          "Choose distinct prerequisites from this project, excluding the task itself.",
        stale_schedule:
          "The project, task, eligibility or time boundary changed. Refresh and preview again.",
        schedule_affects_started_task:
          "This change affects work that has already started. It requires the later revision workflow.",
        schedule_task_not_plannable:
          "Only pending tasks with an eligible active assignee can be scheduled.",
        schedule_calendar_unavailable:
          "The project's pinned calendar rules are unavailable. No dates were guessed.",
        schedule_limit:
          "This project exceeds the supported 250-task scheduling window.",
      };
      return NextResponse.json(
        {
          error:
            messages[error.reason] ??
            "Schedule rejected. Refresh, review your authority and preview again.",
        },
        { status: 409 },
      );
    }
    return NextResponse.json(
      {
        error: "Scheduling is temporarily unavailable. Please try again later.",
      },
      { status: 503 },
    );
  }
}
