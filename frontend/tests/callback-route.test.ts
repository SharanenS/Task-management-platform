// @vitest-environment node

import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  cookieGet,
  cookieDelete,
  getDel,
  authorizationCodeGrant,
  fetchEmployeeProfile,
  createSession,
} = vi.hoisted(() => ({
  cookieGet: vi.fn<() => { value: string } | undefined>(() => ({
    value: "transaction-id",
  })),
  cookieDelete: vi.fn(),
  getDel: vi.fn(),
  authorizationCodeGrant: vi.fn(),
  fetchEmployeeProfile: vi.fn(),
  createSession: vi.fn(),
}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: cookieGet,
    delete: cookieDelete,
  })),
}));
vi.mock("@/auth/redis", () => ({
  getRedis: vi.fn(async () => ({ getDel })),
}));
vi.mock("@/auth/oidc", () => ({
  getOidcConfiguration: vi.fn(() => ({})),
  oidc: { authorizationCodeGrant },
}));
vi.mock("@/auth/gateway", () => ({
  fetchEmployeeProfile,
  ProfileAccessDeniedError: class ProfileAccessDeniedError extends Error {},
}));
vi.mock("@/auth/session", () => ({ createSession }));

import { GET } from "@/app/auth/callback/route";
import { ProfileAccessDeniedError } from "@/auth/gateway";

describe("OIDC callback", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    cookieGet.mockReturnValue({ value: "transaction-id" });
    getDel.mockResolvedValue(
      JSON.stringify({
        codeVerifier: "verifier",
        state: "expected-state",
        nonce: "expected-nonce",
        returnTo: "/system",
      }),
    );
    authorizationCodeGrant.mockResolvedValue({
      access_token: "access-token",
      refresh_token: "refresh-token",
    });
    fetchEmployeeProfile.mockResolvedValue({
      id: "employee-id",
      displayName: "Local User",
      email: "local.user@example.test",
      role: "ADMIN",
    });
  });

  it("consumes a one-time transaction and enforces state, nonce, and PKCE", async () => {
    const response = await GET(
      new NextRequest(
        "http://localhost:3010/auth/callback?code=authorization-code&state=expected-state",
      ),
    );

    expect(getDel).toHaveBeenCalledWith("auth-transaction:transaction-id");
    expect(authorizationCodeGrant).toHaveBeenCalledWith(
      {},
      expect.any(URL),
      expect.objectContaining({
        pkceCodeVerifier: "verifier",
        expectedState: "expected-state",
        expectedNonce: "expected-nonce",
        idTokenExpected: true,
      }),
    );
    expect(createSession).toHaveBeenCalledOnce();
    expect(response.headers.get("location")).toBe(
      "http://localhost:3010/system",
    );
    expect(cookieDelete).toHaveBeenCalled();
  });

  it("returns a sanitized failure when validation fails", async () => {
    const sensitiveValues = [
      "SECRET-NAME-7821",
      "SECRET-CODE-4936",
      "SECRET-MESSAGE-1508",
      "SECRET-CAUSE-6247",
      "SECRET-NESTED-9352",
    ];
    const nested = new Error(sensitiveValues[4]);
    const cause = new Error(sensitiveValues[3], { cause: nested });
    Object.assign(cause, { code: "OAUTH_INVALID_RESPONSE" });
    const failure = new Error(sensitiveValues[2], { cause });
    failure.name = sensitiveValues[0];
    Object.assign(failure, { code: sensitiveValues[1] });
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    authorizationCodeGrant.mockRejectedValueOnce(failure);
    const response = await GET(
      new NextRequest(
        "http://localhost:3010/auth/callback?code=bad&state=expected-state",
      ),
    );

    expect(consoleError).toHaveBeenCalledWith(
      "OIDC callback failed.",
      "AUTHORIZATION_RESPONSE_INVALID",
    );
    const logged = JSON.stringify(consoleError.mock.calls);
    for (const sensitive of sensitiveValues)
      expect(logged).not.toContain(sensitive);
    expect(logged).not.toContain("Error:");
    expect(logged).not.toContain("at ");
    expect(response.headers.get("location")).toBe(
      "http://localhost:3010/sign-in?error=callback",
    );
    expect(createSession).not.toHaveBeenCalled();
  });

  it("uses a fixed unknown category for unrecognized nested errors", async () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    authorizationCodeGrant.mockRejectedValueOnce({
      name: "PRIVATE-NAME",
      code: "PRIVATE-CODE",
      message: "PRIVATE-MESSAGE",
      cause: { message: "PRIVATE-CAUSE", cause: new Error("PRIVATE-NESTED") },
    });

    const response = await GET(
      new NextRequest(
        "http://localhost:3010/auth/callback?code=bad&state=expected-state",
      ),
    );

    expect(consoleError).toHaveBeenCalledWith(
      "OIDC callback failed.",
      "UNKNOWN",
    );
    expect(JSON.stringify(consoleError.mock.calls)).not.toMatch(
      /PRIVATE|Error:|at /,
    );
    expect(response.headers.get("location")).toBe(
      "http://localhost:3010/sign-in?error=callback",
    );
  });

  it("preserves the access-denied redirect without callback diagnostics", async () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    authorizationCodeGrant.mockResolvedValueOnce({
      access_token: "access-token",
    });
    fetchEmployeeProfile.mockRejectedValueOnce(new ProfileAccessDeniedError());

    const response = await GET(
      new NextRequest(
        "http://localhost:3010/auth/callback?code=denied&state=expected-state",
      ),
    );

    expect(response.headers.get("location")).toBe(
      "http://localhost:3010/access-denied",
    );
    expect(consoleError).not.toHaveBeenCalled();
  });

  it("classifies missing, consumed, and mismatched transactions with fixed values", async () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    cookieGet.mockReturnValueOnce(undefined);
    await GET(new NextRequest("http://localhost:3010/auth/callback"));
    expect(consoleError).toHaveBeenLastCalledWith(
      "OIDC callback failed.",
      "TRANSACTION_MISSING",
    );

    getDel.mockResolvedValueOnce(null);
    await GET(new NextRequest("http://localhost:3010/auth/callback"));
    expect(consoleError).toHaveBeenLastCalledWith(
      "OIDC callback failed.",
      "TRANSACTION_ALREADY_CONSUMED",
    );

    await GET(
      new NextRequest(
        "http://localhost:3010/auth/callback?code=code&state=unexpected",
      ),
    );
    expect(consoleError).toHaveBeenLastCalledWith(
      "OIDC callback failed.",
      "STATE_VALIDATION_FAILED",
    );
    expect(authorizationCodeGrant).not.toHaveBeenCalled();
  });

  it("uses fixed profile and session failure categories without leaking errors", async () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    fetchEmployeeProfile.mockRejectedValueOnce(
      new Error("PRIVATE-PROFILE-DETAIL"),
    );
    await GET(
      new NextRequest(
        "http://localhost:3010/auth/callback?code=code&state=expected-state",
      ),
    );
    expect(consoleError).toHaveBeenLastCalledWith(
      "OIDC callback failed.",
      "EMPLOYEE_PROFILE_LOOKUP_FAILED",
    );

    fetchEmployeeProfile.mockResolvedValueOnce({
      id: "employee-id",
      displayName: "Local User",
      email: "local.user@example.test",
      role: "ADMIN",
    });
    createSession.mockRejectedValueOnce(new Error("PRIVATE-SESSION-DETAIL"));
    await GET(
      new NextRequest(
        "http://localhost:3010/auth/callback?code=code&state=expected-state",
      ),
    );
    expect(consoleError).toHaveBeenLastCalledWith(
      "OIDC callback failed.",
      "SESSION_CREATION_FAILED",
    );
    expect(JSON.stringify(consoleError.mock.calls)).not.toContain("PRIVATE-");
  });
});
