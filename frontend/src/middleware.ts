import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { unsealData } from "iron-session";
import { SessionData, getSessionOptions, sessionCookieConfig } from "@/lib/session";

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Paths exempt from authentication
  if (
    pathname === "/login" ||
    pathname === "/auth/callback" ||
    pathname === "/logout" ||
    pathname.startsWith("/_next") ||
    pathname === "/favicon.ico" ||
    /\.(.*)$/.test(pathname)
  ) {
    return NextResponse.next();
  }

  const sessionCookie = request.cookies.get(sessionCookieConfig.cookieName)?.value;

  let hasValidSession = false;
  if (sessionCookie) {
    try {
      const session = await unsealData<SessionData>(sessionCookie, {
        password: getSessionOptions().password,
      });

      if (session?.accessToken) {
        const now = Math.floor(Date.now() / 1000);
        const expiresAt = session.expiresAt || 0;
        const isExpired = expiresAt > 0 && now + 30 >= expiresAt;

        // If access token is expired and there is no refresh token, session is invalid
        if (isExpired && !session.refreshToken) {
          hasValidSession = false;
        } else {
          hasValidSession = true;
        }
      }
    } catch {
      hasValidSession = false;
    }
  }

  if (!hasValidSession) {
    if (pathname.startsWith("/api/")) {
      return NextResponse.json(
        { detail: "Not authenticated" },
        { status: 401 }
      );
    }
    const loginUrl = new URL("/login", request.url);
    const returnTo = pathname + request.nextUrl.search;
    if (returnTo && returnTo !== "/") {
      loginUrl.searchParams.set("returnTo", returnTo);
    }
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
