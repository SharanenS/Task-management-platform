import { NextRequest, NextResponse } from "next/server";
import { sameOrigin } from "@/shared/auth/policy";
import { authConfig } from "@/shared/auth/config";
import { currentSession } from "@/shared/auth/session";
import { accountEntry, AccountDenied } from "@/shared/api/account-entry";
import {
  administrationRequest,
  ProjectChangeRejected,
} from "@/shared/api/account-administration";
import { ChangeTaskDocument } from "@/shared/api/generated";

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
    const result = await administrationRequest(session, ChangeTaskDocument, {
      input: value.input,
    });
    return NextResponse.json(result.changeTask, {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    if (error instanceof AccountDenied)
      return NextResponse.json({ error: "Access denied" }, { status: 403 });
    if (error instanceof SyntaxError)
      return NextResponse.json({ error: "Invalid request" }, { status: 400 });
    if (error instanceof ProjectChangeRejected) {
      const messages: Record<string, string> = {
        stale_task:
          "This project or task changed. Refresh and review before saving again.",
        task_assignee_ineligible:
          "The selected person is no longer an eligible project member. Refresh the member list.",
        task_assignment_unchanged: "Choose a different eligible assignee.",
        task_request_conflict:
          "This request changed. Refresh and review before saving.",
        task_lifecycle_requires_review:
          "This task has moved beyond initial planning. Its history is retained.",
        invalid_task:
          "Complete all required fields and confirm this planning change.",
      };
      return NextResponse.json(
        {
          error:
            messages[error.reason] ??
            "Task change rejected. Refresh and review your project authority.",
        },
        { status: 409 },
      );
    }
    return NextResponse.json(
      { error: "Task services are unavailable. Please try again later." },
      { status: 503 },
    );
  }
}
