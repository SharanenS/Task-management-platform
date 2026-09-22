import { describe, it, expect, vi, beforeEach } from "vitest";
import * as client from "openid-client";
import { getValidAccessToken, setOidcConfigForTesting } from "../lib/oidc";

vi.mock("openid-client", () => {
  return {
    refreshTokenGrant: vi.fn(),
    discovery: vi.fn(async () => ({
      serverMetadata: () => ({ issuer: "http://localhost:8080/realms/enterprise" }),
    })),
    allowInsecureRequests: vi.fn(),
  };
});

let mockSessionA: {
  accessToken?: string;
  refreshToken?: string;
  expiresAt?: number;
  save: ReturnType<typeof vi.fn>;
  destroy: ReturnType<typeof vi.fn>;
};

let mockSessionB: {
  accessToken?: string;
  refreshToken?: string;
  expiresAt?: number;
  save: ReturnType<typeof vi.fn>;
  destroy: ReturnType<typeof vi.fn>;
};

let currentSession = "A";

vi.mock("../lib/session", () => ({
  getSession: vi.fn(async () => {
    return currentSession === "A" ? mockSessionA : mockSessionB;
  }),
  sessionOptions: {
    cookieName: "task_platform_session",
    password: "test-secret-that-is-at-least-32-chars-long",
  },
}));

describe("Concurrent Refresh Token Deduplication", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.KEYCLOAK_CLIENT_SECRET = "mock_secret_for_tests";

    setOidcConfigForTesting({
      serverMetadata: () => ({ issuer: "http://localhost:8080/realms/enterprise" }),
    } as unknown as client.Configuration);

    mockSessionA = {
      accessToken: "expired_token_user_a",
      refreshToken: "refresh_token_user_a",
      expiresAt: Math.floor(Date.now() / 1000) - 100, // expired
      save: vi.fn(async () => {}),
      destroy: vi.fn(),
    };

    mockSessionB = {
      accessToken: "expired_token_user_b",
      refreshToken: "refresh_token_user_b",
      expiresAt: Math.floor(Date.now() / 1000) - 100, // expired
      save: vi.fn(async () => {}),
      destroy: vi.fn(),
    };

    currentSession = "A";
  });

  it("deduplicates concurrent refresh calls for the same session", async () => {
    let resolveGrant!: (value: unknown) => void;
    const delayedPromise = new Promise((resolve) => {
      resolveGrant = resolve;
    });

    vi.mocked(client.refreshTokenGrant).mockReturnValue(
      delayedPromise as unknown as ReturnType<typeof client.refreshTokenGrant>
    );

    // Trigger two concurrent getValidAccessToken calls for User A
    const call1 = getValidAccessToken();
    const call2 = getValidAccessToken();

    // Allow microtasks to run so getOidcConfig resolves and initiates refreshTokenGrant
    await new Promise((r) => setTimeout(r, 10));

    // Verify refreshTokenGrant was called only ONCE despite two concurrent callers
    expect(client.refreshTokenGrant).toHaveBeenCalledTimes(1);
    expect(client.refreshTokenGrant).toHaveBeenCalledWith(
      expect.anything(),
      "refresh_token_user_a"
    );

    // Resolve the single in-flight grant
    resolveGrant({
      access_token: "new_access_token_a",
      refresh_token: "new_rotated_refresh_token_a",
      expires_in: 300,
    });

    const [token1, token2] = await Promise.all([call1, call2]);

    expect(token1).toBe("new_access_token_a");
    expect(token2).toBe("new_access_token_a");
    expect(client.refreshTokenGrant).toHaveBeenCalledTimes(1);
    expect(mockSessionA.save).toHaveBeenCalled();
  });

  it("does not leak or mix tokens across concurrent different-user requests", async () => {
    let resolveA!: (value: unknown) => void;
    const promiseA = new Promise((resolve) => {
      resolveA = resolve;
    });

    let resolveB!: (value: unknown) => void;
    const promiseB = new Promise((resolve) => {
      resolveB = resolve;
    });

    vi.mocked(client.refreshTokenGrant).mockImplementation(async (_config, rt) => {
      if (rt === "refresh_token_user_a") {
        return promiseA as unknown as ReturnType<typeof client.refreshTokenGrant>;
      } else {
        return promiseB as unknown as ReturnType<typeof client.refreshTokenGrant>;
      }
    });

    // Start User A's call
    currentSession = "A";
    const callA = getValidAccessToken();

    // Allow User A's call to register in-flight
    await new Promise((r) => setTimeout(r, 10));

    // Start User B's call
    currentSession = "B";
    const callB = getValidAccessToken();

    // Allow User B's call to register in-flight
    await new Promise((r) => setTimeout(r, 10));

    // Both users should have their own refresh in flight (distinct keys)
    expect(client.refreshTokenGrant).toHaveBeenCalledTimes(2);
    expect(client.refreshTokenGrant).toHaveBeenCalledWith(
      expect.anything(),
      "refresh_token_user_a"
    );
    expect(client.refreshTokenGrant).toHaveBeenCalledWith(
      expect.anything(),
      "refresh_token_user_b"
    );

    // Resolve User A and User B with distinct tokens
    resolveA({
      access_token: "token_for_user_a_only",
      refresh_token: "rotated_rt_a",
      expires_in: 300,
    });
    resolveB({
      access_token: "token_for_user_b_only",
      refresh_token: "rotated_rt_b",
      expires_in: 300,
    });

    const [resA, resB] = await Promise.all([callA, callB]);

    expect(resA).toBe("token_for_user_a_only");
    expect(resB).toBe("token_for_user_b_only");
  });

  it("destroys session and returns null when refresh fails", async () => {
    vi.mocked(client.refreshTokenGrant).mockRejectedValueOnce(
      new Error("Invalid refresh token")
    );

    currentSession = "A";
    const token = await getValidAccessToken();

    expect(token).toBeNull();
    expect(mockSessionA.destroy).toHaveBeenCalled();
  });
});
