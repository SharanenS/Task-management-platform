import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

const projectRoot = dirname(fileURLToPath(import.meta.url));

const trustedKeycloakOrigins = new Set<string>();

const rawIssuer = process.env.OIDC_ISSUER;
if (rawIssuer) {
  try {
    const parsed = new URL(rawIssuer);
    trustedKeycloakOrigins.add(parsed.origin);
    const port = parsed.port || (parsed.protocol === "https:" ? "443" : "80");
    if (parsed.hostname === "localhost") {
      trustedKeycloakOrigins.add(`${parsed.protocol}//127.0.0.1:${port}`);
    } else if (parsed.hostname === "127.0.0.1") {
      trustedKeycloakOrigins.add(`${parsed.protocol}//localhost:${port}`);
    }
  } catch {
    // preserve default loopback origins
  }
}

if (trustedKeycloakOrigins.size === 0) {
  trustedKeycloakOrigins.add("http://localhost:8080");
  trustedKeycloakOrigins.add("http://127.0.0.1:8080");
}

const keycloakOriginsStr = Array.from(trustedKeycloakOrigins).join(" ");

const cspDirectives = [
  `default-src 'self' blob: ${keycloakOriginsStr}`,
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self' blob: http://localhost:8000 http://127.0.0.1:8000 ${keycloakOriginsStr} http://127.0.0.1:3001 http://127.0.0.1:16686 http://127.0.0.1:9090 ws://localhost:3000 ws://127.0.0.1:3000 ws://localhost:3010 ws://127.0.0.1:3010`,
  "frame-ancestors 'none'",
  "base-uri 'self'",
  `form-action 'self' ${keycloakOriginsStr}`,
].join("; ");

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  turbopack: {
    root: projectRoot,
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Content-Security-Policy", value: cspDirectives },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};
export default nextConfig;
