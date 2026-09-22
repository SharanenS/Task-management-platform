import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock openid-client discovery for oidc tests
vi.mock("openid-client", () => {
  return {
    discovery: vi.fn(async () => ({
      serverMetadata: () => ({ issuer: "http://localhost:8180/realms/enterprise" }),
    })),
    allowInsecureRequests: vi.fn(),
  };
});

describe("Secret Validation (Startup / First-use Fail-Loud)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("SESSION_SECRET validation in session.ts", () => {
    it("throws a loud error when SESSION_SECRET is missing", async () => {
      const { getSessionOptions } = await import("@/lib/session");
      const orig = process.env.SESSION_SECRET;
      try {
        delete process.env.SESSION_SECRET;
        expect(() => getSessionOptions()).toThrowError(
          /SESSION_SECRET environment variable is missing/
        );
      } finally {
        process.env.SESSION_SECRET = orig;
      }
    });

    it("throws a loud error when SESSION_SECRET is shorter than 32 characters", async () => {
      const { getSessionOptions } = await import("@/lib/session");
      const orig = process.env.SESSION_SECRET;
      try {
        process.env.SESSION_SECRET = "too-short-secret-123";
        expect(() => getSessionOptions()).toThrowError(
          /SESSION_SECRET environment variable must be at least 32 characters long/
        );
      } finally {
        process.env.SESSION_SECRET = orig;
      }
    });

    it("succeeds when SESSION_SECRET is at least 32 characters long", async () => {
      const { getSessionOptions } = await import("@/lib/session");
      const orig = process.env.SESSION_SECRET;
      try {
        process.env.SESSION_SECRET = "a-valid-session-secret-that-is-32-chars-long!";
        const opts = getSessionOptions();
        expect(opts.password).toBe("a-valid-session-secret-that-is-32-chars-long!");
        expect(opts.cookieName).toBe("task_platform_session");
      } finally {
        process.env.SESSION_SECRET = orig;
      }
    });
  });

  describe("KEYCLOAK_CLIENT_SECRET validation in oidc.ts", () => {
    it("throws a loud error when KEYCLOAK_CLIENT_SECRET is missing", async () => {
      const { getOidcConfig, setOidcConfigForTesting } = await import("@/lib/oidc");
      setOidcConfigForTesting(null);
      const orig = process.env.KEYCLOAK_CLIENT_SECRET;
      try {
        delete process.env.KEYCLOAK_CLIENT_SECRET;
        await expect(getOidcConfig()).rejects.toThrowError(
          /KEYCLOAK_CLIENT_SECRET environment variable is missing/
        );
      } finally {
        process.env.KEYCLOAK_CLIENT_SECRET = orig;
      }
    });

    it("succeeds when KEYCLOAK_CLIENT_SECRET is provided", async () => {
      const { getOidcConfig, setOidcConfigForTesting } = await import("@/lib/oidc");
      setOidcConfigForTesting(null);
      const orig = process.env.KEYCLOAK_CLIENT_SECRET;
      try {
        process.env.KEYCLOAK_CLIENT_SECRET = "my-valid-keycloak-client-secret";
        const config = await getOidcConfig();
        expect(config).toBeDefined();
      } finally {
        process.env.KEYCLOAK_CLIENT_SECRET = orig;
      }
    });
  });
});
