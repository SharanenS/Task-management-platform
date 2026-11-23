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
  CreateCoordinationDocument,
  FollowUpCoordinationDocument,
} from "@/shared/api/generated";

export async function POST(request: NextRequest) {
  if (!sameOrigin(request.headers.get("origin"), authConfig().origin))
    return NextResponse.json({ error: "Request rejected" }, { status: 403 });
  if (Number(request.headers.get("content-length") ?? 0) > 20000)
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
    if (!["ADMIN", "MANAGER"].includes(actor.companyRoles[0]))
      throw new AccountDenied();
    const value = await request.json();
    if (value.command === "create")
      await administrationRequest(session, CreateCoordinationDocument, {
        input: value.input,
      });
    else if (value.command === "follow-up")
      await administrationRequest(session, FollowUpCoordinationDocument, {
        input: value.input,
      });
    else
      return NextResponse.json({ error: "Invalid command" }, { status: 400 });
    return NextResponse.json(
      { saved: true },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch (error) {
    if (error instanceof AccountDenied)
      return NextResponse.json({ error: "Access denied" }, { status: 403 });
    if (error instanceof SyntaxError)
      return NextResponse.json({ error: "Invalid request" }, { status: 400 });
    if (error instanceof ProjectChangeRejected) {
      const messages: Record<string, string> = {
        coordination_recipient_ineligible:
          "A recipient is no longer an active employee appointed to this project. Refresh and review recipients.",
        coordination_stale:
          "This request changed. Refresh before recording another follow-up.",
        invalid_coordination_time: "Choose a valid future date and time.",
        coordination_follow_up_limit:
          "This request has reached its follow-up limit.",
      };
      return NextResponse.json(
        {
          error:
            messages[error.reason] ??
            "Request rejected. Review all fields and current project access.",
        },
        { status: 409 },
      );
    }
    return NextResponse.json(
      {
        error:
          "Coordination services are unavailable. Refresh to check the recorded outcome before retrying.",
      },
      { status: 503 },
    );
  }
}
