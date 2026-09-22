import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";

// Mock openid-client
vi.mock("openid-client", () => {
  return {
    randomPKCECodeVerifier: vi.fn(() => "test_code_verifier_12345"),
    calculatePKCECodeChallenge: vi.fn(async () => "test_code_challenge_67890"),
    randomState: vi.fn(() => "test_random_state_abcdef"),
    buildAuthorizationUrl: vi.fn(
      (_config, params: Record<string, string>) =>
        new URL(
          `http://keycloak:8080/realms/enterprise/protocol/openid-connect/auth?code_challenge=${params.code_challenge}&state=${params.state}`
        )
    ),
    buildEndSessionUrl: vi.fn(
      (_config, params: Record<string, string>) =>
        new URL(
          `http://keycloak:8080/realms/enterprise/protocol/openid-connect/logout?id_token_hint=${params.id_token_hint}`
        )
    ),
    authorizationCodeGrant: vi.fn(async () => ({
      access_token: "mock_access_token_xyz",
      refresh_token: "mock_refresh_token_uvw",
      id_token: "mock_id_token_rst",
      expires_in: 300,
      claims: () => ({
        sub: "user-uuid-1",
        preferred_username: "admin",
        roles: ["ADMIN"],
      }),
    })),
    discovery: vi.fn(async () => ({
      serverMetadata: () => ({ issuer: "http://localhost:8080/realms/enterprise" }),
    })),
    allowInsecureRequests: vi.fn(),
  };
});

// Mock session
const mockSession = {
  accessToken: undefined as string | undefined,
  refreshToken: undefined as string | undefined,
  idToken: undefined as string | undefined,
  expiresAt: undefined as number | undefined,
  idTokenClaims: undefined as Record<string, unknown> | undefined,
  save: vi.fn(async () => {}),
  destroy: vi.fn(() => {
    mockSession.accessToken = undefined;
    mockSession.refreshToken = undefined;
    mockSession.idToken = undefined;
    mockSession.expiresAt = undefined;
    mockSession.idTokenClaims = undefined;
  }),
};

vi.mock("@/lib/session", () => ({
  getSession: vi.fn(async () => mockSession),
  sessionOptions: {
    cookieName: "task_platform_session",
    password: "test-secret-that-is-at-least-32-chars-long",
  },
}));

// Mock oidc getOidcConfig
vi.mock("@/lib/oidc", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/oidc")>();
  return {
    ...actual,
    getOidcConfig: vi.fn(async () => ({
      serverMetadata: () => ({ issuer: "http://localhost:8080/realms/enterprise" }),
    })),
  };
});

import { GET as loginHandler } from "@/app/login/route";
import { GET as callbackHandler } from "@/app/auth/callback/route";
import { POST as logoutHandler } from "@/app/logout/route";

describe("OIDC Authentication Route Handlers", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("GET /login", () => {
    it("redirects (302) to Keycloak auth URL and sets auth state cookie", async () => {
      const request = new NextRequest("http://localhost:3000/login?returnTo=/projects");
      const response = await loginHandler(request);

      expect(response.status).toBe(302);
      const location = response.headers.get("location");
      expect(location).toContain("http://keycloak:8080/realms/enterprise");
      expect(location).toContain("code_challenge=test_code_challenge_67890");
      expect(location).toContain("state=test_random_state_abcdef");

      // Verify cookie
      const authCookie = response.cookies.get("task_platform_auth_state");
      expect(authCookie).toBeDefined();
      const parsed = JSON.parse(authCookie!.value);
      expect(parsed.code_verifier).toBe("test_code_verifier_12345");
      expect(parsed.state).toBe("test_random_state_abcdef");
      expect(parsed.returnTo).toBe("/projects");
    });
  });

  describe("GET /auth/callback", () => {
    it("returns 400 when auth state cookie is missing", async () => {
      const request = new NextRequest("http://localhost:3000/auth/callback?code=abc&state=xyz");
      const response = await callbackHandler(request);

      expect(response.status).toBe(400);
      const text = await response.text();
      expect(text).toContain("Missing authentication verification state");
    });

    it("returns 400 when state query parameter mismatches cookie state", async () => {
      const request = new NextRequest("http://localhost:3000/auth/callback?code=abc&state=wrong_state");
      request.cookies.set(
        "task_platform_auth_state",
        JSON.stringify({
          code_verifier: "test_verifier",
          state: "correct_state",
        })
      );
      const response = await callbackHandler(request);

      expect(response.status).toBe(400);
      const text = await response.text();
      expect(text).toContain("State parameter mismatch or CSRF detected");
    });

    it("exchanges authorization code, populates session, deletes state cookie, and redirects", async () => {
      const request = new NextRequest(
        "http://localhost:3000/auth/callback?code=valid_code&state=expected_state"
      );
      request.cookies.set(
        "task_platform_auth_state",
        JSON.stringify({
          code_verifier: "test_code_verifier_12345",
          state: "expected_state",
          returnTo: "/projects",
        })
      );

      const response = await callbackHandler(request);

      expect(response.status).toBe(302);
      expect(response.headers.get("location")).toBe("http://localhost:3000/projects");

      // Verify session was saved
      expect(mockSession.save).toHaveBeenCalled();
      expect(mockSession.accessToken).toBe("mock_access_token_xyz");
      expect(mockSession.refreshToken).toBe("mock_refresh_token_uvw");
      expect(mockSession.idToken).toBe("mock_id_token_rst");

      // Verify state cookie was cleared
      const deletedCookie = response.cookies.get("task_platform_auth_state");
      expect(deletedCookie?.value).toBe("");
      expect(new Date(deletedCookie?.expires ?? 0).getTime()).toBe(0);
    });
  });

  describe("POST /logout", () => {
    it("destroys session and redirects to Keycloak RP-initiated logout", async () => {
      mockSession.idToken = "mock_id_token_rst";
      const request = new NextRequest("http://localhost:3000/logout", { method: "POST" });
      const response = await logoutHandler(request);

      expect(mockSession.destroy).toHaveBeenCalled();
      expect(response.status).toBe(302);
      const location = response.headers.get("location");
      expect(location).toContain("http://keycloak:8080/realms/enterprise/protocol/openid-connect/logout");
      expect(location).toContain("id_token_hint=mock_id_token_rst");
    });
  });
});
