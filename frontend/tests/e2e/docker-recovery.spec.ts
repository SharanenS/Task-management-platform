import { execFile } from "node:child_process";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { test, expect } from "@playwright/test";

const execute = promisify(execFile);
const composeFile = fileURLToPath(
  new URL("../../../compose.yaml", import.meta.url),
);

test("real gateway container outage and recovery", async ({
  page,
}, testInfo) => {
  test.skip(
    process.env.RUN_DOCKER_RECOVERY !== "1" ||
      testInfo.project.name !== "desktop",
    "Opt-in, isolated Docker recovery check",
  );
  test.setTimeout(90_000);
  const compose = (action: string) =>
    execute("docker", ["compose", "-f", composeFile, action, "gateway"], {
      timeout: 30_000,
    });
  await page.goto("/system");
  await expect(
    page.getByRole("heading", { name: "Gateway is reachable" }),
  ).toBeVisible();
  try {
    await compose("stop");
    await page.getByRole("button", { name: "Refresh status" }).click();
    await expect(page.getByRole("main").getByRole("alert")).toContainText(
      "Gateway unavailable",
    );
    await expect(
      page.getByText("Gateway connected", { exact: true }),
    ).toHaveCount(0);
    await page.screenshot({
      path: testInfo.outputPath("gateway-outage.png"),
      fullPage: true,
    });
  } finally {
    await compose("start");
  }
  await expect
    .poll(async () => {
      try {
        return (
          await page.request.get("http://127.0.0.1:8010/health/ready")
        ).ok();
      } catch {
        return false;
      }
    })
    .toBe(true);
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(
    page.getByRole("heading", { name: "Gateway is reachable" }),
  ).toBeVisible();
});
