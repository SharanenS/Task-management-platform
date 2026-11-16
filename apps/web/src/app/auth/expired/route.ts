import { NextResponse } from "next/server";
import { authConfig } from "@/shared/auth/config";
import {
  currentSession,
  cookieOptions,
  sessionCookie,
} from "@/shared/auth/session";
export async function GET() {
  const c = authConfig();
  if (!(await sessionCookie()))
    return NextResponse.redirect(new URL("/sign-in", c.origin));
  try {
    if (await currentSession())
      return NextResponse.redirect(new URL("/auth/ready", c.origin));
    const response = NextResponse.redirect(
      new URL("/session-expired", c.origin),
    );
    response.cookies.set(c.sessionCookie, "", cookieOptions(0));
    response.headers.set("Cache-Control", "no-store");
    return response;
  } catch {
    return NextResponse.redirect(new URL("/session-unavailable", c.origin));
  }
}
