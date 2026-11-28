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
  ExecuteTaskDocument,
  ReviewCompletionDocument,
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
    if (!["EMPLOYEE", "MANAGER", "ADMIN"].includes(actor.companyRoles[0]))
      throw new AccountDenied();
    const value = await request.json();
    if (value.action === "execute") {
      if (actor.companyRoles[0] !== "EMPLOYEE") throw new AccountDenied();
      const result = await administrationRequest(session, ExecuteTaskDocument, {
        input: value.input,
      });
      return NextResponse.json(result.executeTask, {
        headers: { "Cache-Control": "no-store" },
      });
    }
    if (value.action === "decide") {
      const result = await administrationRequest(
        session,
        ReviewCompletionDocument,
        { input: value.input },
      );
      return NextResponse.json(result.reviewCompletion, {
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
        explicit_self_approval_required:
          "Confirm that you are approving your own submission. This is recorded as self-approval.",
        explicit_fallback_required:
          "An active review-scoped absence record is required for owner or administrator fallback.",
        stale_review:
          "The submission, assignment or project changed. Refresh and review the current submission.",
        stale_task: "The task or project changed. Refresh before continuing.",
        task_prerequisites_not_ready:
          "A known schedule, reached start date and completed prerequisites are required. Planned dates stay unchanged.",
        task_execution_state:
          "This action is not available in the current task state.",
        task_assignee_ineligible:
          "The current assignee must be an active eligible project member.",
      };
      return NextResponse.json(
        {
          error:
            messages[error.reason] ??
            "Request rejected. Refresh and check your current task authority and confirmation.",
        },
        { status: 409 },
      );
    }
    return NextResponse.json(
      {
        error:
          "Review services are unavailable. Check the recorded outcome before retrying.",
      },
      { status: 503 },
    );
  }
}
