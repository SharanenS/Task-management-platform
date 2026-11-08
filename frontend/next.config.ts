import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

const projectRoot = dirname(fileURLToPath(import.meta.url));

const cspDirectives = [
  "default-src 'self' blob: http://localhost:8080 http://127.0.0.1:8080",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self' blob: http://localhost:8000 http://127.0.0.1:8000 http://localhost:8080 http://127.0.0.1:8080 http://127.0.0.1:3001 http://127.0.0.1:16686 http://127.0.0.1:9090 ws://localhost:3000 ws://127.0.0.1:3000 ws://localhost:3010 ws://127.0.0.1:3010",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self' http://localhost:8080 http://127.0.0.1:8080",
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
