import type { NextConfig } from "next";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const applicationRoot = dirname(fileURLToPath(import.meta.url));

const identityOrigin = new URL(
  process.env.AUTH_ISSUER ?? "http://127.0.0.1:8180/realms/taskspace-portals",
).origin;

const config: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: applicationRoot,
  poweredByHeader: false,
  experimental: { cpus: 2 },
  logging: { incomingRequests: false },
  turbopack: { root: applicationRoot },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Cache-Control", value: "no-store" },
          {
            key: "Content-Security-Policy",
            value: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self' ${identityOrigin}; object-src 'none'`,
          },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default config;
