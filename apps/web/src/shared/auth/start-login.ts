import { NextRequest, NextResponse } from "next/server";
import { authConfig } from "@/shared/auth/config";
import { cookieOptions } from "@/shared/auth/session";
import { authStore } from "@/shared/auth/store";
import {
  identifier,
  returnPath,
  sameOrigin,
  storageKey,
  TRANSACTION_TTL,
  validIdentifier,
} from "@/shared/auth/policy";
import { checkProvider, provider, oidc } from "@/shared/auth/provider";

export async function beginLogin(
  request: NextRequest,
  destination?: string,
  expectedSubject?: string,
) {
  const c = authConfig();
  if (!sameOrigin(request.headers.get("origin"), c.origin))
    return new NextResponse("Request rejected", { status: 403 });
  try {
    await checkProvider();
    const old = request.cookies.get(c.transactionCookie)?.value;
    if (validIdentifier(old))
      await authStore.remove(storageKey("transaction", old));
    const form = await request.formData();
    const id = identifier();
    const verifier = oidc.randomPKCECodeVerifier();
    const transaction = {
      state: oidc.randomState(),
      nonce: oidc.randomNonce(),
      verifier,
      returnTo: returnPath(destination ?? String(form.get("returnTo") ?? "")),
      ...(expectedSubject ? { expectedSubject } : {}),
      createdAt: Date.now(),
    };
    const url = oidc.buildAuthorizationUrl(provider(), {
      scope: "openid profile",
      redirect_uri: c.callback,
      state: transaction.state,
      nonce: transaction.nonce,
      code_challenge: await oidc.calculatePKCECodeChallenge(verifier),
      code_challenge_method: "S256",
      prompt: "login",
      ...(expectedSubject ? { kc_action: "UPDATE_PASSWORD" } : {}),
    });
    await authStore.put(
      storageKey("transaction", id),
      JSON.stringify(transaction),
      TRANSACTION_TTL,
    );
    const response = NextResponse.redirect(url, 303);
    response.cookies.set(
      c.transactionCookie,
      id,
      cookieOptions(TRANSACTION_TTL),
    );
    response.headers.set("Cache-Control", "no-store");
    return response;
  } catch {
    console.error("Authentication failed: login_dependency");
    return NextResponse.redirect(
      new URL("/sign-in?status=unavailable", c.origin),
      303,
    );
  }
}
