import { describe, it, expect } from "vitest";
import { NextRequest } from "next/server";
import { getBaseUrl, getSafeRedirectUrl } from "../lib/url";

describe("URL Utilities", () => {
  it("replaces 0.0.0.0 with localhost", () => {
    const req = new NextRequest("http://0.0.0.0:3000/some/path", {
      headers: { host: "0.0.0.0:3000" },
    });
    expect(getBaseUrl(req)).toBe("http://localhost:3000");
  });

  it("respects x-forwarded-host and x-forwarded-proto", () => {
    const req = new NextRequest("http://127.0.0.1:3000/some/path", {
      headers: {
        "x-forwarded-host": "app.example.com",
        "x-forwarded-proto": "https",
      },
    });
    expect(getBaseUrl(req)).toBe("https://app.example.com");
  });

  it("safely creates redirect URL with fallback", () => {
    const req = new NextRequest("http://localhost:3000/auth/callback", {
      headers: { host: "localhost:3000" },
    });

    const safeUrl = getSafeRedirectUrl("/projects", req);
    expect(safeUrl.toString()).toBe("http://localhost:3000/projects");

    // Rejects open redirect attempts
    const unsafeUrl = getSafeRedirectUrl("//evil.com", req, "/");
    expect(unsafeUrl.toString()).toBe("http://localhost:3000/");
  });
});
