// @vitest-environment node

import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  cookieDelete,
  getDel,
  authorizationCodeGrant,
  fetchEmployeeProfile,
  createSession,
} = vi.hoisted(() => ({
  cookieDelete: vi.fn(),
  getDel: vi.fn(),
  authorizationCodeGrant: vi.fn(),
  fetchEmployeeProfile: vi.fn(),
  createSession: vi.fn(),
}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: vi.fn(() => ({ value: "transaction-id" })),
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

describe("OIDC callback", () => {
  beforeEach(() => {
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
    authorizationCodeGrant.mockRejectedValueOnce(new Error("sensitive detail"));
    const response = await GET(
      new NextRequest("http://localhost:3010/auth/callback?code=bad"),
    );

    expect(response.headers.get("location")).toBe(
      "http://localhost:3010/sign-in?error=callback",
    );
    expect(createSession).not.toHaveBeenCalled();
  });
});
