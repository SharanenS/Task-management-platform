import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 45_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  use: {
    baseURL: "http://127.0.0.1:3020",
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    {
      name: "tablet",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 768, height: 1024 },
      },
    },
    {
      name: "mobile",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 390, height: 844 },
      },
    },
  ],
  reporter: [["./tests/safe-reporter.ts"]],
});
