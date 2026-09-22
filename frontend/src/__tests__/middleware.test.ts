import { describe, it, expect, beforeEach } from "vitest";
import { NextRequest } from "next/server";
import { middleware } from "@/middleware";
import { sealData } from "iron-session";
import { sessionOptions, SessionData } from "@/lib/session";

describe("Frontend Auth Middleware", () => {
  beforeEach(() => {
    process.env.SESSION_SECRET = "test-session-secret-must-be-at-least-32-chars-long";
  });

  it("bypasses /login without redirect", async () => {
    const request = new NextRequest("http://localhost:3000/login");
    const response = await middleware(request);
    expect(response.status).toBe(200);
    expect(response.headers.get("location")).toBeNull();
  });

  it("bypasses /auth/callback without redirect", async () => {
    const request = new NextRequest("http://localhost:3000/auth/callback?code=abc&state=xyz");
    const response = await middleware(request);
    expect(response.status).toBe(200);
    expect(response.headers.get("location")).toBeNull();
  });

  it("bypasses /logout without redirect", async () => {
    const request = new NextRequest("http://localhost:3000/logout");
    const response = await middleware(request);
    expect(response.status).toBe(200);
    expect(response.headers.get("location")).toBeNull();
  });

  it("redirects unauthenticated user from /projects to /login?returnTo=/projects", async () => {
    const request = new NextRequest("http://localhost:3000/projects");
    const response = await middleware(request);
    expect(response.status).toBe(307);
    const location = response.headers.get("location");
    expect(location).toContain("/login");
    expect(location).toContain("returnTo=%2Fprojects");
  });

  it("returns 401 for unauthenticated /api/ requests", async () => {
    const request = new NextRequest("http://localhost:3000/api/backend/api/v1/jobs");
    const response = await middleware(request);
    expect(response.status).toBe(401);
    const body = await response.json();
    expect(body.detail).toBe("Not authenticated");
  });

  it("allows access when valid, unexpired session cookie is present", async () => {
    const validSession: SessionData = {
      accessToken: "mock_jwt_token",
      expiresAt: Math.floor(Date.now() / 1000) + 3600,
    };

    const sealed = await sealData(validSession, {
      password: sessionOptions.password,
    });

    const request = new NextRequest("http://localhost:3000/projects");
    request.cookies.set(sessionOptions.cookieName, sealed);

    const response = await middleware(request);
    expect(response.status).toBe(200);
    expect(response.headers.get("location")).toBeNull();
  });

  it("redirects to /login when access token is expired and no refresh token is present", async () => {
    const expiredSessionNoRefresh: SessionData = {
      accessToken: "mock_expired_token",
      expiresAt: Math.floor(Date.now() / 1000) - 100, // Expired in the past
    };

    const sealed = await sealData(expiredSessionNoRefresh, {
      password: sessionOptions.password,
    });

    const request = new NextRequest("http://localhost:3000/projects");
    request.cookies.set(sessionOptions.cookieName, sealed);

    const response = await middleware(request);
    expect(response.status).toBe(307);
    const location = response.headers.get("location");
    expect(location).toContain("/login");
    expect(location).toContain("returnTo=%2Fprojects");
  });

  it("redirects to /login when access token is within 30s buffer and no refresh token is present", async () => {
    const expiringSoonSession: SessionData = {
      accessToken: "mock_expiring_token",
      expiresAt: Math.floor(Date.now() / 1000) + 15, // Expiring in 15s (within 30s buffer)
    };

    const sealed = await sealData(expiringSoonSession, {
      password: sessionOptions.password,
    });

    const request = new NextRequest("http://localhost:3000/projects");
    request.cookies.set(sessionOptions.cookieName, sealed);

    const response = await middleware(request);
    expect(response.status).toBe(307);
    const location = response.headers.get("location");
    expect(location).toContain("/login");
  });

  it("allows access when access token is expired but valid refresh token is present (to allow proxy refresh)", async () => {
    const expiredSessionWithRefresh: SessionData = {
      accessToken: "mock_expired_token",
      refreshToken: "mock_usable_refresh_token",
      expiresAt: Math.floor(Date.now() / 1000) - 100,
    };

    const sealed = await sealData(expiredSessionWithRefresh, {
      password: sessionOptions.password,
    });

    const request = new NextRequest("http://localhost:3000/projects");
    request.cookies.set(sessionOptions.cookieName, sealed);

    const response = await middleware(request);
    expect(response.status).toBe(200);
    expect(response.headers.get("location")).toBeNull();
  });
});
