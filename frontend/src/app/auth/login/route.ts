import { randomUUID } from "node:crypto";

import { NextRequest, NextResponse } from "next/server";

import { authConfig, TRANSACTION_COOKIE } from "@/auth/config";
import {
  assertOidcAvailable,
  getOidcConfiguration,
  oidc,
  OidcUnavailableError,
} from "@/auth/oidc";
import { getRedis } from "@/auth/redis";
import { safeReturnPath } from "@/auth/return-path";
import type { AuthTransaction } from "@/auth/types";

export async function GET(request: NextRequest) {
  try {
    await assertOidcAvailable();
    const codeVerifier = oidc.randomPKCECodeVerifier();
    const transaction: AuthTransaction = {
      codeVerifier,
      state: oidc.randomState(),
      nonce: oidc.randomNonce(),
      returnTo: safeReturnPath(request.nextUrl.searchParams.get("returnTo")),
    };
    const transactionId = randomUUID();
    await (
      await getRedis()
    ).set(`auth-transaction:${transactionId}`, JSON.stringify(transaction), {
      expiration: { type: "EX", value: 600 },
    });
    const authorizationUrl = oidc.buildAuthorizationUrl(
      getOidcConfiguration(),
      {
        redirect_uri: new URL(
          "/auth/callback",
          authConfig.appBaseUrl,
        ).toString(),
        scope: "openid email profile",
        response_type: "code",
        code_challenge: await oidc.calculatePKCECodeChallenge(codeVerifier),
        code_challenge_method: "S256",
        state: transaction.state,
        nonce: transaction.nonce,
      },
    );
    const response = NextResponse.redirect(authorizationUrl);
    response.cookies.set(TRANSACTION_COOKIE, transactionId, {
      httpOnly: true,
      secure: authConfig.secureCookies,
      sameSite: "lax",
      path: "/auth/callback",
      maxAge: 600,
    });
    return response;
  } catch (error) {
    if (!(error instanceof OidcUnavailableError)) throw error;
    console.error("OIDC login initiation failed.", error.name);
    return NextResponse.redirect(
      new URL("/sign-in?error=unavailable", authConfig.appBaseUrl),
    );
  }
}
