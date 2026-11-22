import { NextRequest, NextResponse } from "next/server";
import { sameOrigin } from "@/shared/auth/policy";
import { authConfig } from "@/shared/auth/config";
import { currentSession } from "@/shared/auth/session";
import { accountEntry, AccountDenied } from "@/shared/api/account-entry";
import {
  administrationRequest,
  ProjectChangeRejected,
} from "@/shared/api/account-administration";
import { ChangeProjectMembershipDocument } from "@/shared/api/generated";

export async function POST(request: NextRequest) {
  if (!sameOrigin(request.headers.get("origin"), authConfig().origin))
    return NextResponse.json({ error: "Request rejected" }, { status: 403 });
  if (Number(request.headers.get("content-length") ?? 0) > 20000)
    return NextResponse.json(
      { error: "Membership change is too large" },
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
      return NextResponse.json({ error: "Access denied" }, { status: 403 });
    const input = await request.json();
    const result = (
      await administrationRequest(session, ChangeProjectMembershipDocument, {
        input,
      })
    ).changeProjectMembership;
    return NextResponse.json(
      { result },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch (error) {
    if (error instanceof SyntaxError)
      return NextResponse.json(
        { error: "Invalid membership change" },
        { status: 400 },
      );
    if (error instanceof AccountDenied)
      return NextResponse.json({ error: "Access denied" }, { status: 403 });
    if (error instanceof ProjectChangeRejected) {
      const messages: Record<string, string> = {
        stale_project_membership:
          "Membership changed while you were editing. Refresh and review before confirming again.",
        member_not_eligible:
          "This person needs an active EMPLOYEE account and active employee record before appointment.",
        leader_already_appointed:
          "Demote or remove the current team leader before appointing another.",
        membership_not_active:
          "This appointment is no longer active. Refresh the page.",
        no_membership_change: "This appointment already has these values.",
        project_membership_limit:
          "This project has reached the supported appointment limit.",
      };
      return NextResponse.json(
        {
          error:
            messages[error.reason] ??
            "The membership change was rejected. Refresh and review the current project.",
        },
        { status: 409 },
      );
    }
    return NextResponse.json(
      {
        error:
          "Membership services are unavailable. Refresh to check the recorded outcome before trying again.",
      },
      { status: 503 },
    );
  }
}
