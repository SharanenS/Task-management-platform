// @vitest-environment node

import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const redisSet = vi.fn();

vi.mock("@/auth/redis", () => ({
  getRedis: vi.fn(async () => ({ set: redisSet })),
}));

import { GET } from "@/app/auth/login/route";

describe("login initiation", () => {
  beforeEach(() => {
    redisSet.mockClear();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 200 })),
    );
  });

  it("creates one-time state, nonce, and PKCE values", async () => {
    const response = await GET(
      new NextRequest("http://localhost:3010/auth/login?returnTo=%2Fsystem"),
    );
    expect(response.status).toBe(307);
    const location = new URL(response.headers.get("location")!);
    expect(location.origin).toBe("http://localhost:8080");
    expect(location.searchParams.get("code_challenge_method")).toBe("S256");
    expect(location.searchParams.get("code_challenge")).toBeTruthy();
    expect(location.searchParams.get("state")).toBeTruthy();
    expect(location.searchParams.get("nonce")).toBeTruthy();
    const stored = JSON.parse(redisSet.mock.calls[0][1] as string) as {
      state: string;
      nonce: string;
      codeVerifier: string;
      returnTo: string;
    };
    expect(stored.state).toBe(location.searchParams.get("state"));
    expect(stored.nonce).toBe(location.searchParams.get("nonce"));
    expect(stored.codeVerifier).toBeTruthy();
    expect(stored.returnTo).toBe("/system");
    expect(response.headers.get("set-cookie")).toContain("HttpOnly");
    expect(response.headers.get("set-cookie")).toContain("SameSite=lax");
  });

  it("rejects an external return target", async () => {
    await GET(
      new NextRequest(
        "http://localhost:3010/auth/login?returnTo=https%3A%2F%2Fattacker.example",
      ),
    );
    const stored = JSON.parse(redisSet.mock.calls[0][1] as string) as {
      returnTo: string;
    };
    expect(stored.returnTo).toBe("/");
  });

  it("returns a sanitized unavailable state when Keycloak cannot be reached", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Promise.reject(new TypeError("offline"))),
    );
    const response = await GET(
      new NextRequest("http://localhost:3010/auth/login?returnTo=%2F"),
    );
    expect(response.headers.get("location")).toBe(
      "http://localhost:3010/sign-in?error=unavailable",
    );
    expect(redisSet).not.toHaveBeenCalled();
  });

  it("does not hide unrelated application errors", async () => {
    redisSet.mockRejectedValueOnce(new Error("programming failure"));
    await expect(
      GET(new NextRequest("http://localhost:3010/auth/login?returnTo=%2F")),
    ).rejects.toThrow("programming failure");
  });
});
