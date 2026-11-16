import { NextRequest, NextResponse } from "next/server";
import { authConfig } from "@/shared/auth/config";
import { authStore } from "@/shared/auth/store";
import { cookieOptions } from "@/shared/auth/session";
import {
  readSession,
  sameOrigin,
  storageKey,
  validIdentifier,
} from "@/shared/auth/policy";
import { checkProvider, oidc, provider } from "@/shared/auth/provider";

export async function POST(request: NextRequest) {
  const c = authConfig();
  if (!sameOrigin(request.headers.get("origin"), c.origin))
    return new NextResponse("Request rejected", { status: 403 });
  const id = request.cookies.get(c.sessionCookie)?.value;
  let destination = new URL("/signed-out", c.origin);
  try {
    const session = await readSession(authStore, id);
    if (validIdentifier(id)) await authStore.remove(storageKey("session", id));
    if (session) {
      try {
        await checkProvider();
        destination = oidc.buildEndSessionUrl(provider(), {
          id_token_hint: session.idToken,
          post_logout_redirect_uri: destination.href,
          client_id: c.clientId,
        });
      } catch {
        destination = new URL("/signed-out?status=provider", c.origin);
      }
    }
  } catch {
    console.error("Authentication failed: logout_store");
    // Keep the cookie so the user can retry revocation; never report successful logout.
    return NextResponse.redirect(
      new URL("/session-unavailable?status=logout", c.origin),
      303,
    );
  }
  const response = NextResponse.redirect(destination, 303);
  response.cookies.set(c.sessionCookie, "", cookieOptions(0));
  response.cookies.set(c.transactionCookie, "", cookieOptions(0));
  response.headers.set("Cache-Control", "no-store");
  return response;
}
