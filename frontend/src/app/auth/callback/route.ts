import { NextRequest, NextResponse } from "next/server";
import * as client from "openid-client";
import { getOidcConfig } from "@/lib/oidc";
import { getSession } from "@/lib/session";

export async function GET(request: NextRequest) {
  try {
    const authStateCookie = request.cookies.get("task_platform_auth_state")?.value;
    if (!authStateCookie) {
      return new NextResponse("Missing authentication verification state", {
        status: 400,
      });
    }

    let parsedState: { code_verifier: string; state: string; returnTo?: string };
    try {
      parsedState = JSON.parse(authStateCookie);
    } catch {
      return new NextResponse("Invalid authentication verification state", {
        status: 400,
      });
    }

    const { code_verifier, state, returnTo = "/" } = parsedState;

    const url = new URL(request.url);
    const paramState = url.searchParams.get("state");
    if (!paramState || paramState !== state) {
      return new NextResponse("State parameter mismatch or CSRF detected", {
        status: 400,
      });
    }

    const config = await getOidcConfig();

    const host = request.headers.get("host") || "localhost:3000";
    const protocol =
      request.headers.get("x-forwarded-proto") ||
      (host.includes("localhost") ? "http" : "https");
    const currentUrl = new URL(
      `${protocol}://${host}${request.nextUrl.pathname}${request.nextUrl.search}`
    );

    if (currentUrl.searchParams.has("iss")) {
      currentUrl.searchParams.set("iss", config.serverMetadata().issuer);
    }
    const tokenResponse = await client.authorizationCodeGrant(
      config,
      currentUrl,
      {
        pkceCodeVerifier: code_verifier,
        expectedState: state,
      }
    );

    const session = await getSession();
    session.accessToken = tokenResponse.access_token;
    session.refreshToken = tokenResponse.refresh_token;
    session.idToken = tokenResponse.id_token;
    session.expiresAt =
      Math.floor(Date.now() / 1000) + (tokenResponse.expires_in || 300);

    try {
      await session.save();
    } catch (saveErr) {
      // If encrypted session cookie exceeds 4096-byte limit with idToken included,
      // retain essential accessToken and refreshToken for proxy authentication
      if (session.idToken) {
        delete session.idToken;
        await session.save();
      } else {
        throw saveErr;
      }
    }

    // Prevent open redirect: ensure returnTo starts with '/' and does not start with '//'
    const safeReturnTo =
      returnTo.startsWith("/") && !returnTo.startsWith("//") ? returnTo : "/";
    const redirectUrl = new URL(safeReturnTo, request.url);
    const response = NextResponse.redirect(redirectUrl, 302);
    response.cookies.delete("task_platform_auth_state");

    return response;
  } catch (error) {
    console.error("Authentication callback failed:", error);
    return new NextResponse("Authentication failed during token exchange", {
      status: 500,
    });
  }
}
