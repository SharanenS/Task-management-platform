import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { authConfig, CSRF_COOKIE } from "@/auth/config";
import { getOidcConfiguration, oidc } from "@/auth/oidc";
import { deleteSession, getSession } from "@/auth/session";

export async function POST(request: NextRequest) {
  const session = await getSession();
  if (!session)
    return NextResponse.json({ logoutUrl: "/sign-in?error=logged_out" });
  const csrfHeader = request.headers.get("x-csrf-token") ?? "";
  const csrfCookie = (await cookies()).get(CSRF_COOKIE)?.value ?? "";
  if (
    !csrfHeader ||
    csrfHeader !== csrfCookie ||
    csrfHeader !== session.record.csrfToken
  )
    return NextResponse.json(
      { error: "Invalid logout request" },
      { status: 403 },
    );
  const record = await deleteSession(session.id);
  const parameters: Record<string, string> = {
    post_logout_redirect_uri: new URL(
      "/signed-out",
      authConfig.appBaseUrl,
    ).toString(),
    client_id: authConfig.clientId,
  };
  if (record?.idToken) parameters.id_token_hint = record.idToken;
  const logoutUrl = oidc.buildEndSessionUrl(getOidcConfiguration(), parameters);
  return NextResponse.json({ logoutUrl: logoutUrl.toString() });
}
