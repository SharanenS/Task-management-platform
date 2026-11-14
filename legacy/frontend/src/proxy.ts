import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/auth/config";

export function proxy(request: NextRequest) {
  if (request.cookies.has(SESSION_COOKIE)) return NextResponse.next();
  const signIn = new URL("/sign-in", request.url);
  signIn.searchParams.set(
    "returnTo",
    `${request.nextUrl.pathname}${request.nextUrl.search}`,
  );
  return NextResponse.redirect(signIn);
}

export const config = {
  matcher: ["/", "/system/:path*", "/design-system/:path*"],
};
