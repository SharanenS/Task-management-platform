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
  PreviewOwnerDeadlineDocument,
  RecordOwnerDecisionDocument,
  RecordReviewFallbackDocument,
  RevokeReviewFallbackDocument,
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
    if (value.command === "preview") {
      const result = await administrationRequest(
        session,
        PreviewOwnerDeadlineDocument,
        { input: value.input },
      );
      return NextResponse.json(
        { preview: result.previewOwnerDeadline },
        { headers: { "Cache-Control": "no-store" } },
      );
    }
    if (value.command === "decide")
      await administrationRequest(session, RecordOwnerDecisionDocument, {
        input: value.input,
      });
    else if (value.command === "fallback-create")
      await administrationRequest(session, RecordReviewFallbackDocument, {
        input: value.input,
      });
    else if (value.command === "fallback-revoke")
      await administrationRequest(session, RevokeReviewFallbackDocument, {
        input: value.input,
      });
    else
      return NextResponse.json(
        { error: "Invalid owner command" },
        { status: 400 },
      );
    return NextResponse.json(
      { recorded: true },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch (error) {
    if (error instanceof AccountDenied)
      return NextResponse.json({ error: "Access denied" }, { status: 403 });
    if (error instanceof SyntaxError)
      return NextResponse.json({ error: "Invalid request" }, { status: 400 });
    if (error instanceof ProjectChangeRejected) {
      const messages: Record<string, string> = {
        owner_assessment_required:
          "A fresh delivery assessment is required. No forecast is assumed when an assessment is missing or stale.",
        stale_owner_escalation:
          "This request or project changed. Refresh and review before deciding again.",
        stale_owner_preview:
          "The preview is no longer current. Refresh and preview the deadline again.",
        owner_deadline_before_forecast:
          "Choose a future working-day deadline at or after the assessed forecast.",
        non_working_deadline:
          "Choose a working date in the configured company calendar.",
        invalid_fallback_period:
          "Choose an explicit start and end, with the end in the future.",
        stale_fallback_leader:
          "Project leadership changed. Refresh before recording an absence.",
        fallback_already_revoked:
          "This fallback has already been revoked. Refresh its history.",
      };
      return NextResponse.json(
        {
          error:
            messages[error.reason] ??
            "Owner request rejected. Review the current project, required fields and confirmation.",
        },
        { status: 409 },
      );
    }
    return NextResponse.json(
      {
        error:
          "Owner decision services are unavailable. Refresh to check the recorded outcome before retrying.",
      },
      { status: 503 },
    );
  }
}
