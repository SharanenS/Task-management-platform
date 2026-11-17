import { NextRequest, NextResponse } from "next/server";
import { authConfig } from "@/shared/auth/config";
import { sameOrigin } from "@/shared/auth/policy";
import { currentSession } from "@/shared/auth/session";
import { adminWorkspace, AccountDenied } from "@/shared/api/account-entry";
import {
  administrationRequest,
  AccountChangeRejected,
} from "@/shared/api/account-administration";
import { ChangeOrganizationDocument } from "@/shared/api/generated";
export async function POST(request: NextRequest) {
  const config = authConfig();
  if (!sameOrigin(request.headers.get("origin"), config.origin))
    return new NextResponse("Request rejected", { status: 403 });
  if (Number(request.headers.get("content-length") ?? 0) > 8192)
    return new NextResponse("Request rejected", { status: 413 });
  let destination = "organization";
  const result = (notice: string) =>
    NextResponse.redirect(
      new URL(`/admin/${destination}?notice=${notice}`, config.origin),
      303,
    );
  try {
    const session = await currentSession();
    if (!session)
      return NextResponse.redirect(new URL("/sign-in", config.origin), 303);
    await adminWorkspace(session);
    const form = await request.formData();
    const field = (name: string) => String(form.get(name) ?? "");
    destination =
      field("destination") === "employees" ? "employees" : "organization";
    const action = field("action");
    if (
      ![
        "UNIT_CREATE",
        "UNIT_UPDATE",
        "EMPLOYEE_CREATE",
        "EMPLOYEE_UPDATE",
        "ACCOUNT_LINK",
      ].includes(action)
    )
      return new NextResponse("Request rejected", { status: 400 });
    if (
      ["UNIT_UPDATE", "ACCOUNT_LINK"].includes(action) &&
      field("confirm") !== "yes"
    )
      return result("confirmation");
    await administrationRequest(session, ChangeOrganizationDocument, {
      input: {
        requestId: field("requestId"),
        action,
        entityId: field("entityId") || null,
        version: field("version") ? Number(field("version")) : null,
        kind: field("kind") || null,
        name: field("name") || null,
        active: field("active") ? field("active") === "true" : null,
        departmentId: field("departmentId") || null,
        jobTitleId: field("jobTitleId") || null,
        managerId: field("managerId") || null,
        accountId: field("accountId") || null,
      },
    });
    return result("complete");
  } catch (error) {
    if (error instanceof AccountDenied)
      return new NextResponse("Request rejected", { status: 403 });
    return result(
      error instanceof AccountChangeRejected ? "rejected" : "unavailable",
    );
  }
}
