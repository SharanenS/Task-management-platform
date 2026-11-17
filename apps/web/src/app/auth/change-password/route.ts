import { NextRequest, NextResponse } from "next/server";
import { authConfig } from "@/shared/auth/config";
import { sameOrigin } from "@/shared/auth/policy";
import { currentSession } from "@/shared/auth/session";
import { adminWorkspace, AccountDenied } from "@/shared/api/account-entry";
import { beginLogin } from "@/shared/auth/start-login";
export async function POST(request: NextRequest) {
  const config = authConfig();
  if (!sameOrigin(request.headers.get("origin"), config.origin))
    return new NextResponse("Request rejected", { status: 403 });
  try {
    const session = await currentSession();
    if (!session)
      return NextResponse.redirect(new URL("/sign-in", config.origin), 303);
    try {
      await adminWorkspace(session);
    } catch (error) {
      if (error instanceof AccountDenied)
        return new NextResponse("Request rejected", { status: 403 });
      throw error;
    }
    return beginLogin(request, "/admin/security", session.subject);
  } catch {
    return NextResponse.redirect(
      new URL("/session-unavailable", config.origin),
      303,
    );
  }
}
