import { NextRequest, NextResponse } from "next/server";
import * as client from "openid-client";
import { getOidcConfig } from "@/lib/oidc";

export async function GET(request: NextRequest) {
  try {
    const config = await getOidcConfig();
    const code_verifier = client.randomPKCECodeVerifier();
    const code_challenge = await client.calculatePKCECodeChallenge(code_verifier);
    const state = client.randomState();

    const searchParams = request.nextUrl.searchParams;
    const returnTo = searchParams.get("returnTo") || "/";

    const host = request.headers.get("host") || "localhost:3000";
    const protocol =
      request.headers.get("x-forwarded-proto") ||
      (host.includes("localhost") ? "http" : "https");
    const redirect_uri = `${protocol}://${host}/auth/callback`;

    const authUrl = client.buildAuthorizationUrl(config, {
      redirect_uri,
      scope: "openid profile email roles",
      code_challenge,
      code_challenge_method: "S256",
      state,
    });

    const response = NextResponse.redirect(authUrl.toString(), 302);

    // Save PKCE verifier, state, and returnTo in short-lived HttpOnly cookie (10 mins)
    const authState = JSON.stringify({ code_verifier, state, returnTo });
    response.cookies.set("task_platform_auth_state", authState, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 600,
    });

    return response;
  } catch (error) {
    console.error("Login initiation failed:", error);
    return new NextResponse("Authentication service unavailable", { status: 500 });
  }
}
