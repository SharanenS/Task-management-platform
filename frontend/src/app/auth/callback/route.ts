import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { authConfig, TRANSACTION_COOKIE } from "@/auth/config";
import { fetchEmployeeProfile, ProfileAccessDeniedError } from "@/auth/gateway";
import { getOidcConfiguration, oidc } from "@/auth/oidc";
import { getRedis } from "@/auth/redis";
import { createSession } from "@/auth/session";
import type { AuthTransaction } from "@/auth/types";

export async function GET(request: NextRequest) {
  const store = await cookies();
  const transactionId = store.get(TRANSACTION_COOKIE)?.value;
  store.delete(TRANSACTION_COOKIE);
  if (!transactionId)
    return NextResponse.redirect(
      new URL("/sign-in?error=callback", authConfig.appBaseUrl),
    );
  const redis = await getRedis();
  const raw = await redis.getDel(`auth-transaction:${transactionId}`);
  if (!raw)
    return NextResponse.redirect(
      new URL("/sign-in?error=callback", authConfig.appBaseUrl),
    );
  try {
    const transaction = JSON.parse(raw) as AuthTransaction;
    const callbackUrl = new URL(request.url);
    callbackUrl.protocol = authConfig.appBaseUrl.protocol;
    callbackUrl.host = authConfig.appBaseUrl.host;
    const tokens = await oidc.authorizationCodeGrant(
      getOidcConfiguration(),
      callbackUrl,
      {
        pkceCodeVerifier: transaction.codeVerifier,
        expectedState: transaction.state,
        expectedNonce: transaction.nonce,
        idTokenExpected: true,
      },
    );
    if (!tokens.access_token) throw new Error("Access token missing");
    const employee = await fetchEmployeeProfile(tokens.access_token);
    await createSession(tokens, employee);
    return NextResponse.redirect(
      new URL(transaction.returnTo, authConfig.appBaseUrl),
    );
  } catch (error) {
    if (error instanceof ProfileAccessDeniedError)
      return NextResponse.redirect(
        new URL("/access-denied", authConfig.appBaseUrl),
      );
    return NextResponse.redirect(
      new URL("/sign-in?error=callback", authConfig.appBaseUrl),
    );
  }
}
