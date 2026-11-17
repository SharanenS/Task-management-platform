import { NextRequest, NextResponse } from "next/server";
import { authConfig } from "@/shared/auth/config";
import { authStore } from "@/shared/auth/store";
import { cookieOptions } from "@/shared/auth/session";
import {
  consumeTransaction,
  identifier,
  sessionLifetime,
  storageKey,
  validIdentifier,
} from "@/shared/auth/policy";
import { provider, oidc } from "@/shared/auth/provider";

export async function GET(request: NextRequest) {
  const c = authConfig();
  const failure = () => {
    const response = NextResponse.redirect(
      new URL("/sign-in?status=interrupted", c.origin),
    );
    response.cookies.set(c.transactionCookie, "", cookieOptions(0));
    response.headers.set("Cache-Control", "no-store");
    return response;
  };
  try {
    const query = request.nextUrl.searchParams;
    if (["state", "code", "error"].some((key) => query.getAll(key).length > 1))
      throw new Error("Ambiguous callback");
    const transaction = await consumeTransaction(
      authStore,
      request.cookies.get(c.transactionCookie)?.value,
      query.get("state"),
    );
    if (query.has("error") || !query.get("code")) return failure();
    const callback = new URL(c.callback);
    callback.search = request.nextUrl.search;
    const tokens = await oidc.authorizationCodeGrant(provider(), callback, {
      pkceCodeVerifier: transaction.verifier,
      expectedState: transaction.state,
      expectedNonce: transaction.nonce,
      idTokenExpected: true,
    });
    const claims = tokens.claims();
    if (
      !tokens.access_token ||
      !tokens.id_token ||
      !claims?.sub ||
      !claims.exp ||
      !tokens.expires_in
    )
      throw new Error("Invalid identity response");
    if (
      transaction.expectedSubject &&
      claims.sub !== transaction.expectedSubject
    )
      throw new Error("Identity action subject mismatch");
    const ttl = sessionLifetime(tokens.expires_in, claims.exp);
    if (ttl < 1) throw new Error("Expired identity response");
    const old = request.cookies.get(c.sessionCookie)?.value;
    if (validIdentifier(old))
      await authStore.remove(storageKey("session", old));
    const id = identifier();
    await authStore.put(
      storageKey("session", id),
      JSON.stringify({
        subject: claims.sub,
        displayName:
          typeof claims.name === "string"
            ? claims.name.slice(0, 150)
            : "Your account",
        accessToken: tokens.access_token,
        idToken: tokens.id_token,
        expiresAt: Date.now() + ttl * 1000,
      }),
      ttl,
    );
    const response = NextResponse.redirect(
      new URL(transaction.returnTo, c.origin),
    );
    response.cookies.set(c.transactionCookie, "", cookieOptions(0));
    response.cookies.set(c.sessionCookie, id, cookieOptions(ttl));
    response.headers.set("Cache-Control", "no-store");
    return response;
  } catch {
    console.error("Authentication failed: callback_rejected");
    return failure();
  }
}
