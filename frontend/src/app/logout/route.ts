import { NextRequest, NextResponse } from "next/server";
import * as client from "openid-client";
import { getOidcConfig } from "@/lib/oidc";
import { getSession } from "@/lib/session";

async function handleLogout(request: NextRequest) {
  try {
    const session = await getSession();
    const idToken = session.idToken;

    session.destroy();

    const host = request.headers.get("host") || "localhost:3000";
    const protocol =
      request.headers.get("x-forwarded-proto") ||
      (host.includes("localhost") ? "http" : "https");
    const postLogoutRedirectUri = `${protocol}://${host}/login`;

    try {
      const config = await getOidcConfig();
      const params: Record<string, string> = {
        post_logout_redirect_uri: postLogoutRedirectUri,
      };
      if (idToken) {
        params.id_token_hint = idToken;
      } else {
        params.client_id = process.env.KEYCLOAK_CLIENT_ID || "task-platform";
      }
      const endSessionUrl = client.buildEndSessionUrl(config, params);
      return NextResponse.redirect(endSessionUrl.toString(), 302);
    } catch (err) {
      console.warn("Could not build RP-initiated logout URL:", err);
    }

    return NextResponse.redirect(new URL("/login", request.url), 302);
  } catch (error) {
    console.error("Logout error:", error);
    return NextResponse.redirect(new URL("/login", request.url), 302);
  }
}

export async function POST(request: NextRequest) {
  return handleLogout(request);
}

export async function GET(request: NextRequest) {
  return handleLogout(request);
}
