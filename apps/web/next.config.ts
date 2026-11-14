import type { NextConfig } from "next";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const applicationRoot = dirname(fileURLToPath(import.meta.url));

const config: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: applicationRoot,
  poweredByHeader: false,
  turbopack: { root: applicationRoot },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default config;
