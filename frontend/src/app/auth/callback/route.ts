import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { authConfig, TRANSACTION_COOKIE } from "@/auth/config";
import { fetchEmployeeProfile, ProfileAccessDeniedError } from "@/auth/gateway";
import { getOidcConfiguration, oidc } from "@/auth/oidc";
import { getRedis } from "@/auth/redis";
import { createSession } from "@/auth/session";
import type { AuthTransaction } from "@/auth/types";

const CALLBACK_DIAGNOSTIC = {
  TRANSACTION_MISSING: "TRANSACTION_MISSING",
  TRANSACTION_ALREADY_CONSUMED: "TRANSACTION_ALREADY_CONSUMED",
  STATE_VALIDATION_FAILED: "STATE_VALIDATION_FAILED",
  AUTHORIZATION_RESPONSE_INVALID: "AUTHORIZATION_RESPONSE_INVALID",
  ID_TOKEN_INVALID: "ID_TOKEN_INVALID",
  TOKEN_RESPONSE_INVALID: "TOKEN_RESPONSE_INVALID",
  UPSTREAM_RESPONSE_INVALID: "UPSTREAM_RESPONSE_INVALID",
  UPSTREAM_TIMEOUT: "UPSTREAM_TIMEOUT",
  EMPLOYEE_PROFILE_LOOKUP_FAILED: "EMPLOYEE_PROFILE_LOOKUP_FAILED",
  SESSION_CREATION_FAILED: "SESSION_CREATION_FAILED",
  UNKNOWN: "UNKNOWN",
} as const;

type CallbackDiagnostic =
  (typeof CALLBACK_DIAGNOSTIC)[keyof typeof CALLBACK_DIAGNOSTIC];

function readStringProperty(
  value: unknown,
  property: string,
): string | undefined {
  if (
    (typeof value !== "object" || value === null) &&
    typeof value !== "function"
  )
    return undefined;
  try {
    const candidate = Reflect.get(value, property);
    return typeof candidate === "string" ? candidate : undefined;
  } catch {
    return undefined;
  }
}

function readCause(value: unknown): unknown {
  if (
    (typeof value !== "object" || value === null) &&
    typeof value !== "function"
  )
    return undefined;
  try {
    return Reflect.get(value, "cause");
  } catch {
    return undefined;
  }
}

function callbackErrorCategory(error: unknown): CallbackDiagnostic {
  let current = error;
  for (let depth = 0; depth < 4 && current !== undefined; depth += 1) {
    const code = readStringProperty(current, "code");
    if (
      code === "OAUTH_JWT_CLAIM_COMPARISON_FAILED" ||
      code === "OAUTH_JWT_TIMESTAMP_CHECK_FAILED"
    )
      return CALLBACK_DIAGNOSTIC.ID_TOKEN_INVALID;
    if (
      code === "OAUTH_RESPONSE_IS_NOT_JSON" ||
      code === "OAUTH_RESPONSE_IS_NOT_CONFORM"
    )
      return CALLBACK_DIAGNOSTIC.UPSTREAM_RESPONSE_INVALID;
    if (code === "OAUTH_TIMEOUT") return CALLBACK_DIAGNOSTIC.UPSTREAM_TIMEOUT;

    const message = readStringProperty(current, "message")?.toLowerCase();
    if (message?.includes("state") || message?.includes("authorization code"))
      return CALLBACK_DIAGNOSTIC.AUTHORIZATION_RESPONSE_INVALID;
    if (
      message?.includes("nonce") ||
      message?.includes("issuer") ||
      message?.includes("audience") ||
      message?.includes("signature") ||
      message?.includes("jwt")
    )
      return CALLBACK_DIAGNOSTIC.ID_TOKEN_INVALID;
    if (
      message?.includes("access_token") ||
      message?.includes("id_token") ||
      message?.includes("token_type")
    )
      return CALLBACK_DIAGNOSTIC.TOKEN_RESPONSE_INVALID;
    if (message?.includes("response body"))
      return CALLBACK_DIAGNOSTIC.UPSTREAM_RESPONSE_INVALID;
    if (message?.includes("timed out") || message?.includes("timeout"))
      return CALLBACK_DIAGNOSTIC.UPSTREAM_TIMEOUT;
    if (code === "OAUTH_INVALID_RESPONSE")
      return CALLBACK_DIAGNOSTIC.AUTHORIZATION_RESPONSE_INVALID;
    current = readCause(current);
  }
  return CALLBACK_DIAGNOSTIC.UNKNOWN;
}

export async function GET(request: NextRequest) {
  const store = await cookies();
  const transactionId = store.get(TRANSACTION_COOKIE)?.value;
  store.delete(TRANSACTION_COOKIE);
  if (!transactionId) {
    console.error(
      "OIDC callback failed.",
      CALLBACK_DIAGNOSTIC.TRANSACTION_MISSING,
    );
    return NextResponse.redirect(
      new URL("/sign-in?error=callback", authConfig.appBaseUrl),
    );
  }
  const redis = await getRedis();
  const raw = await redis.getDel(`auth-transaction:${transactionId}`);
  if (!raw) {
    console.error(
      "OIDC callback failed.",
      CALLBACK_DIAGNOSTIC.TRANSACTION_ALREADY_CONSUMED,
    );
    return NextResponse.redirect(
      new URL("/sign-in?error=callback", authConfig.appBaseUrl),
    );
  }
  const callbackFailure = (category: CallbackDiagnostic) => {
    console.error("OIDC callback failed.", category);
    return NextResponse.redirect(
      new URL("/sign-in?error=callback", authConfig.appBaseUrl),
    );
  };
  try {
    const transaction = JSON.parse(raw) as AuthTransaction;
    const callbackUrl = new URL(request.url);
    callbackUrl.protocol = authConfig.appBaseUrl.protocol;
    callbackUrl.host = authConfig.appBaseUrl.host;
    if (callbackUrl.searchParams.get("state") !== transaction.state)
      return callbackFailure(CALLBACK_DIAGNOSTIC.STATE_VALIDATION_FAILED);
    if (!callbackUrl.searchParams.get("code"))
      return callbackFailure(
        CALLBACK_DIAGNOSTIC.AUTHORIZATION_RESPONSE_INVALID,
      );
    let tokens;
    try {
      tokens = await oidc.authorizationCodeGrant(
        getOidcConfiguration(),
        callbackUrl,
        {
          pkceCodeVerifier: transaction.codeVerifier,
          expectedState: transaction.state,
          expectedNonce: transaction.nonce,
          idTokenExpected: true,
        },
      );
    } catch (error) {
      return callbackFailure(callbackErrorCategory(error));
    }
    if (!tokens.access_token)
      return callbackFailure(CALLBACK_DIAGNOSTIC.TOKEN_RESPONSE_INVALID);
    let employee;
    try {
      employee = await fetchEmployeeProfile(tokens.access_token);
    } catch (error) {
      if (error instanceof ProfileAccessDeniedError)
        return NextResponse.redirect(
          new URL("/access-denied", authConfig.appBaseUrl),
        );
      return callbackFailure(
        CALLBACK_DIAGNOSTIC.EMPLOYEE_PROFILE_LOOKUP_FAILED,
      );
    }
    try {
      await createSession(tokens, employee);
    } catch {
      return callbackFailure(CALLBACK_DIAGNOSTIC.SESSION_CREATION_FAILED);
    }
    return NextResponse.redirect(
      new URL(transaction.returnTo, authConfig.appBaseUrl),
    );
  } catch {
    return callbackFailure(CALLBACK_DIAGNOSTIC.UNKNOWN);
  }
}
