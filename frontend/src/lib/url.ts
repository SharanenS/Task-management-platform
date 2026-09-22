import { NextRequest } from "next/server";

/**
 * Derives the canonical base URL for browser-facing redirects.
 * Ensures 0.0.0.0 (internal Docker binding) is never sent to browsers.
 */
export function getBaseUrl(request: NextRequest): string {
  const forwardedHost = request.headers.get("x-forwarded-host");
  const hostHeader = request.headers.get("host");
  let host = forwardedHost || hostHeader || "localhost:3000";

  // Replace 0.0.0.0 with localhost for browser compatibility
  host = host.replace(/0\.0\.0\.0/g, "localhost");

  const forwardedProto = request.headers.get("x-forwarded-proto");
  const proto =
    forwardedProto ||
    (host.includes("localhost") || host.includes("127.0.0.1") ? "http" : "https");

  return `${proto}://${host}`;
}

/**
 * Constructs a safe redirect URL ensuring the destination is on the canonical base.
 */
export function getSafeRedirectUrl(
  path: string,
  request: NextRequest,
  defaultPath: string = "/"
): URL {
  const safePath =
    path && path.startsWith("/") && !path.startsWith("//") ? path : defaultPath;
  const baseUrl = getBaseUrl(request);
  const target = new URL(safePath, baseUrl);
  if (target.hostname === "0.0.0.0") {
    target.hostname = "localhost";
  }
  return target;
}
