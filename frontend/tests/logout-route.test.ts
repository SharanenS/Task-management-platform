// @vitest-environment node

import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { getSession, deleteSession, buildEndSessionUrl, cookieState } =
  vi.hoisted(() => ({
    getSession: vi.fn(),
    deleteSession: vi.fn(),
    buildEndSessionUrl: vi.fn(),
    cookieState: { value: "csrf-token" },
  }));

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: vi.fn(() => ({ value: cookieState.value })),
  })),
}));
vi.mock("@/auth/session", () => ({ getSession, deleteSession }));
vi.mock("@/auth/oidc", () => ({
  getOidcConfiguration: vi.fn(() => ({})),
  oidc: { buildEndSessionUrl },
}));

import { POST } from "@/app/auth/logout/route";

describe("logout", () => {
  beforeEach(() => {
    cookieState.value = "csrf-token";
    getSession.mockResolvedValue({
      id: "session-id",
      record: { csrfToken: "csrf-token" },
    });
    deleteSession.mockResolvedValue({ idToken: "id-token" });
    buildEndSessionUrl.mockReturnValue(
      new URL("http://localhost:8080/realms/taskspace/logout"),
    );
  });

  it("rejects a state-changing request without matching CSRF proof", async () => {
    const response = await POST(
      new NextRequest("http://localhost:3010/auth/logout", {
        method: "POST",
        headers: { "x-csrf-token": "wrong" },
      }),
    );
    expect(response.status).toBe(403);
    expect(deleteSession).not.toHaveBeenCalled();
  });

  it("deletes the local session and returns the identity-provider logout URL", async () => {
    const response = await POST(
      new NextRequest("http://localhost:3010/auth/logout", {
        method: "POST",
        headers: { "x-csrf-token": "csrf-token" },
      }),
    );
    expect(deleteSession).toHaveBeenCalledWith("session-id");
    expect(buildEndSessionUrl).toHaveBeenCalledWith(
      {},
      expect.objectContaining({
        id_token_hint: "id-token",
        post_logout_redirect_uri: "http://localhost:3010/signed-out",
      }),
    );
    await expect(response.json()).resolves.toEqual({
      logoutUrl: "http://localhost:8080/realms/taskspace/logout",
    });
  });
});
