import { NextRequest, NextResponse } from "next/server";
import { authConfig } from "@/shared/auth/config";
import { sameOrigin } from "@/shared/auth/policy";
import { currentSession } from "@/shared/auth/session";
import { accountEntry, AccountDenied } from "@/shared/api/account-entry";
import {
  administrationRequest,
  ProjectChangeRejected,
} from "@/shared/api/account-administration";
import {
  PreviewProjectDocument,
  CreateProjectDocument,
} from "@/shared/api/generated";
export async function POST(request: NextRequest) {
  if (!sameOrigin(request.headers.get("origin"), authConfig().origin))
    return NextResponse.json({ error: "Request rejected" }, { status: 403 });
  if (Number(request.headers.get("content-length") ?? 0) > 20000)
    return NextResponse.json(
      { error: "Project details are too large" },
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
    const value = await request.json();
    if (value.action === "preview")
      return NextResponse.json(
        {
          result: (
            await administrationRequest(session, PreviewProjectDocument, {
              input: value.input,
            })
          ).previewProject,
        },
        { headers: { "Cache-Control": "no-store" } },
      );
    if (value.action !== "create")
      return NextResponse.json({ error: "Request rejected" }, { status: 400 });
    const result = (
      await administrationRequest(session, CreateProjectDocument, {
        input: value.input,
      })
    ).createProject;
    const root =
      actor.companyRoles[0] === "ADMIN"
        ? "/admin/projects"
        : "/manager/projects";
    return NextResponse.json(
      { result, href: `${root}/${result.id}` },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch (error) {
    if (error instanceof AccountDenied)
      return NextResponse.json({ error: "Access denied" }, { status: 403 });
    if (error instanceof ProjectChangeRejected) {
      const messages: Record<string, string> = {
        company_calendar_required:
          "Ask your administrator to publish the company calendar first.",
        invalid_project_details:
          "Enter a project name and clear objectives within the length limits.",
        non_working_deadline:
          "The agreed deadline falls on a non-working date. Choose an explicit working date; the deadline has not been moved.",
        stale_project_calendar:
          "The company calendar changed. Refresh and review a new project preview.",
        preview_expired:
          "The preview expired. Review a new preview before creating the project.",
        confirmation_required: "Confirm the objectives and agreed deadline.",
        unsupported_timezone_version:
          "Matching timezone rules are unavailable. Contact the administrator.",
        invalid_date: "Choose a valid deadline date.",
        preview_already_used:
          "This preview already created a project. Refresh the project list.",
        ambiguous_or_nonexistent_time:
          "The calendar hours are ambiguous on this date. Ask the administrator to configure a valid date exception.",
      };
      return NextResponse.json(
        {
          error:
            messages[error.reason] ??
            "The project request was rejected. Refresh and review its current details.",
        },
        { status: 409 },
      );
    }
    return NextResponse.json(
      {
        error:
          "Project services are unavailable. Refresh to check the recorded outcome before trying again.",
      },
      { status: 503 },
    );
  }
}
