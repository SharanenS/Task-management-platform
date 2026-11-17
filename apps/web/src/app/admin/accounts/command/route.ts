import { NextRequest, NextResponse } from "next/server";
import { authConfig } from "@/shared/auth/config";
import { sameOrigin } from "@/shared/auth/policy";
import { currentSession } from "@/shared/auth/session";
import { adminWorkspace, AccountDenied } from "@/shared/api/account-entry";
import {
  administrationRequest,
  AccountChangeRejected,
} from "@/shared/api/account-administration";
import {
  CreateAccountDocument,
  ChangeAccountDocument,
  RecoverAccountDocument,
} from "@/shared/api/generated";
export async function POST(request: NextRequest) {
  const config = authConfig();
  const destination = (notice: string) =>
    NextResponse.redirect(
      new URL(`/admin/accounts?notice=${notice}`, config.origin),
      303,
    );
  if (!sameOrigin(request.headers.get("origin"), config.origin))
    return new NextResponse("Request rejected", { status: 403 });
  if (Number(request.headers.get("content-length") ?? 0) > 8192)
    return new NextResponse("Request rejected", { status: 413 });
  try {
    const session = await currentSession();
    if (!session)
      return NextResponse.redirect(new URL("/sign-in", config.origin), 303);
    await adminWorkspace(session);
    const form = await request.formData();
    const field = (name: string) => String(form.get(name) ?? "");
    const requestId = field("requestId");
    let state: string;
    if (field("intent") === "create") {
      const result = await administrationRequest(
        session,
        CreateAccountDocument,
        {
          input: {
            requestId,
            username: field("username"),
            email: field("email"),
            displayName: field("displayName"),
            role: field("role"),
          },
        },
      );
      state = result.createAccount.state;
    } else if (field("intent") === "recover") {
      if (field("confirm") !== "yes") return destination("confirmation");
      const result = await administrationRequest(
        session,
        RecoverAccountDocument,
        { input: { requestId, operationId: field("operationId") } },
      );
      state = result.recoverAccount.state;
    } else if (field("intent") === "change") {
      if (field("confirm") !== "yes") return destination("confirmation");
      const result = await administrationRequest(
        session,
        ChangeAccountDocument,
        {
          input: {
            requestId,
            accountId: field("accountId"),
            version: Number(field("version")),
            action: field("action"),
            role: field("role") || null,
          },
        },
      );
      state = result.changeAccount.state;
    } else return new NextResponse("Request rejected", { status: 400 });
    return destination(state === "COMPLETE" ? "complete" : "incomplete");
  } catch (error) {
    if (error instanceof AccountDenied)
      return new NextResponse("Request rejected", { status: 403 });
    if (error instanceof AccountChangeRejected) return destination("rejected");
    return destination("unavailable");
  }
}
